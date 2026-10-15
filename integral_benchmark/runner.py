"""Process-isolated engine protocol with separate solver and verifier budgets."""

from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import math
import threading
from .model import ROOT, digest, load_cases

SOLVER_FIELDS = ("schema_version", "id", "kind", "integrand", "variable", "domains",
                 "assumptions", "bounds", "contour", "branches")
STATUSES = {"answer", "answer-untranslated", "unevaluated", "conditional", "divergent",
            "undefined", "unsupported-kind", "unsupported-assumptions", "translation-error", "error"}


def harness_digest():
    package = Path(__file__).parent
    return digest({p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(package.rglob('*')) if p.suffix in {'.py', '.mjs', '.json'}})


def invoke(command, request, timeout, env=None):
    start = time.perf_counter()
    try:
        completed = subprocess.run(command, input=json.dumps(request), capture_output=True,
                                   text=True, encoding="utf-8", timeout=timeout, cwd=ROOT,
                                   env={**os.environ, **(env or {})}, shell=False)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "wall_ms": (time.perf_counter() - start) * 1000}
    except OSError as exc:
        return {"status": "launch-error", "reason": str(exc), "wall_ms": (time.perf_counter() - start) * 1000}
    wall = (time.perf_counter() - start) * 1000
    if completed.returncode:
        return {"status": "process-error", "reason": completed.stderr[-1500:], "wall_ms": wall}
    try:
        response = json.loads(completed.stdout)
        if not isinstance(response, dict): raise ValueError("Response must be one JSON object")
    except (ValueError, TypeError):
        return {"status": "protocol-error", "reason": completed.stdout[-1500:], "wall_ms": wall}
    return {**response, "wall_ms": wall}


def run(corpus, output, engine, timeout=10, verify_timeout=5, jobs=1, limit=None,
        ce_root=None, node="node", external=None, rules=False, seed=20261003, ce_module=None,
        ce_rules_module=None, resume=False, batch_size=None, setup_timeout=120,
        rule_step_budget=300000, stop_event=None, prepared_corpus=None,
        verifier_mode='fresh', verifier_recycle=100):
    import random
    if any(not math.isfinite(x) or x <= 0 for x in (timeout, verify_timeout, setup_timeout)):
        raise ValueError('Timeouts must be positive finite values')
    if rule_step_budget < 0: raise ValueError('Rule step budget must be nonnegative')
    if verifier_mode not in {'fresh', 'warm'}: raise ValueError('Unknown verifier mode')
    if type(verifier_recycle) is not int or verifier_recycle < 1:
        raise ValueError('Verifier recycle count must be a positive integer')
    if prepared_corpus is not None:
        cases, corpus_hash = prepared_corpus.for_path(corpus)
    else:
        cases = load_cases(corpus)
        corpus_hash = digest(cases)
    # Family-round-robin selection avoids taking only the first source/chapter.
    if limit is not None:
        groups = {}
        for c in cases: groups.setdefault(c["family"], []).append(c)
        rng = random.Random(seed)
        for group in groups.values(): rng.shuffle(group)
        selected = []
        while len(selected) < limit and any(groups.values()):
            for family in sorted(groups):
                if groups[family] and len(selected) < limit: selected.append(groups[family].pop())
        cases = selected
    env = {}
    version = {}
    if engine == "sympy":
        command = [sys.executable, "-m", "integral_benchmark.sympy_worker"]
        import sympy
        version = {"version": sympy.__version__}
    elif engine == "ce":
        if any(k.startswith('RUBI_') for k in os.environ):
            raise ValueError('Unset RUBI_* environment overrides; baseline rule settings must be explicit')
        if not ce_root: raise ValueError("--ce-root is required")
        ce_root = Path(ce_root).resolve()
        module = Path(ce_module).resolve() if ce_module else ce_root / "src/compute-engine/index.ts"
        rules_module = Path(ce_rules_module).resolve() if ce_rules_module else ce_root / "src/integration-rules.ts"
        tsx = ce_root / "node_modules/tsx/dist/loader.mjs"
        needs_tsx = not ce_module or (rules and not ce_rules_module)
        if not module.is_file() or (needs_tsx and not tsx.is_file()) or (rules and not rules_module.is_file()):
            raise ValueError("CE module and required tsx dependency are missing")
        command = [node, *(["--import", tsx.as_uri()] if needs_tsx else []), str(Path(__file__).parent / "adapters/ce.mjs")]
        env["CE_MODULE"] = str(module)
        env['CE_RULES_MODULE'] = ''
        env['CE_PHASED'] = '1'
        env['CE_STEP_BUDGET'] = str(rule_step_budget)
        env['CE_RULE_TIME_MS'] = str(timeout * 1000)
        if rules:
            env["CE_RULES_MODULE"] = str(rules_module)
        version = {"revision": subprocess.check_output(["git", "-C", str(ce_root), "rev-parse", "HEAD"], text=True).strip(),
                   "dirty": bool(subprocess.check_output(["git", "-C", str(ce_root), "status", "--porcelain"], text=True).strip()),
                   "rules": rules,
                   "runtime": subprocess.check_output([node, "--version"], text=True).strip()}
        if ce_module:
            version["module_sha256"] = hashlib.sha256(module.read_bytes()).hexdigest()
            version["load_mode"] = "caller-built-bundle"
        else:
            version["load_mode"] = "source-tsx"
        if rules:
            version['rules_module_sha256'] = hashlib.sha256(rules_module.read_bytes()).hexdigest()
            version['rules_load_mode'] = 'caller-built-bundle' if ce_rules_module else 'source-tsx'
            version['rules_options'] = {'stepBudget': rule_step_budget, 'timeLimitMs': timeout * 1000}
    else:
        if not external: raise ValueError("External engine requires --command-json with an executable argv array")
        command = json.loads(external)
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise ValueError("Command must be an argv array")
        version = {"command_digest": digest(command), "version": "adapter-reported-see-results"}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    import sympy
    metadata = {"schema_version": 2, "engine": engine + ("-rubi" if rules else ""),
                "engine_identity": version, "started_utc": datetime.now(timezone.utc).isoformat(),
                "platform": platform.system(), "architecture": platform.machine(),
                "python": platform.python_version(), "logical_cpus": os.cpu_count(),
                "timeout_seconds": timeout, "verification_timeout_seconds": verify_timeout,
                'setup_timeout_seconds': setup_timeout if engine == 'ce' else None,
                "jobs": jobs, "case_count": len(cases), "corpus_sha256": corpus_hash,
                "selected_ids": [c["id"] for c in cases], "selection_seed": seed,
                "isolation": "fresh process per case; CE setup and solve have separate hard budgets",
                "verifier": "SymPy " + sympy.__version__, "independent_engine_verifier": engine != "sympy",
                'verifier_mode': verifier_mode,
                'verifier_recycle': verifier_recycle if verifier_mode == 'warm' else None,
                'verification_budget_semantics': 'request wall time including spawn/import when a new worker is needed',
                "memory_limit": "not-enforced", "repeats": 1,
                "comparison_warning": "Cold-start coverage run; parallel contention and one repetition preclude performance rankings",
                'assumptions_status_counts': dict(Counter(c.get('assumptions_status', 'explicit-case-contract') for c in cases)),
                'parameter_cases': sum(bool(c.get('parameters')) for c in cases),
                'branch_verification': 'restricted identities are separate from unrestricted local derivative identities'}
    metadata['harness_sha256'] = harness_digest()
    pinned_modules = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                      ([module] + ([rules_module] if rules else []) if engine == 'ce' else [])}
    local = threading.local()
    verifiers = []
    verifier_lock = threading.Lock()

    def check(request):
        if verifier_mode == 'fresh':
            return invoke([sys.executable, '-m', 'integral_benchmark.verifier'], request, verify_timeout)
        if not hasattr(local, 'verifier'):
            from .warm_verifier import WarmVerifier
            local.verifier = WarmVerifier(verifier_recycle)
            with verifier_lock:
                verifiers.append(local.verifier)
        return local.verifier.invoke(request, verify_timeout)

    def one(case):
        if stop_event is not None and stop_event.is_set():
            raise RuntimeError('Paired baseline interrupted; completed evidence preserved')
        if harness_digest() != metadata['harness_sha256']:
            raise RuntimeError('Harness changed during the run; stop rather than mix implementations')
        if any(hashlib.sha256(p.read_bytes()).hexdigest() != sha for p, sha in pinned_modules.items()):
            raise RuntimeError('CE module changed during the run; use a new run directory')
        solver_case = {k: case[k] for k in SOLVER_FIELDS if k in case}
        if engine == 'ce':
            from .phased import invoke_phased
            result = invoke_phased(command, {'protocol_version': 2, 'case': solver_case}, setup_timeout, timeout, env)
        else:
            result = invoke(command, {"protocol_version": 1, "case": solver_case}, timeout, env)
        if result.get("status") not in STATUSES | {"timeout", "setup-timeout", "setup-error", "launch-error", "process-error", "protocol-error"}:
            result = {"status": "protocol-error", "reason": "Unknown adapter status"}
        if result.get("status") == "answer" and "answer" not in result:
            result = {"status": "protocol-error", "reason": "Missing answer"}
        if result['status'] in {'setup-timeout', 'setup-error', 'launch-error', 'process-error', 'protocol-error'}:
            verification = {'verdict': 'infrastructure-error', 'wall_ms': 0}
        elif result["status"] not in {"answer", "conditional"} and case["expected"]["status"] not in {"divergent", "undefined"}:
            verification = {"verdict": "not-solved", "wall_ms": 0}
        else:
            verification = check({'case': case, 'result': result})
        if "verdict" not in verification:
            verification["verdict"] = "verification-timeout" if verification.get("status") == "timeout" else "verifier-error"
        return {"id": case["id"], "family": case["family"], "kind": case["kind"],
                'assumptions_status': case.get('assumptions_status', 'explicit-case-contract'),
                'parameter_case': bool(case.get('parameters')),
                "case_sha256": digest(case), "result": result, "verification": verification}

    from .checkpoint import execute
    try:
        return execute(output, metadata, cases, one, jobs, resume, batch_size)
    finally:
        # execute's worker threads have joined, including on errors. No request
        # can race this cleanup or deliver a late result to a subsequent run.
        for verifier in verifiers:
            verifier.close()
