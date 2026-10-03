"""Process-isolated engine protocol with separate solver and verifier budgets."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from .model import ROOT, digest, load_cases, write_json

SOLVER_FIELDS = ("schema_version", "id", "kind", "integrand", "variable", "domains",
                 "assumptions", "bounds", "contour", "branches")
STATUSES = {"answer", "answer-untranslated", "unevaluated", "conditional", "divergent",
            "undefined", "unsupported-kind", "unsupported-assumptions", "translation-error", "error"}


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
        ce_root=None, node="node", external=None, rules=False, seed=20261003, ce_module=None):
    import random
    cases = load_cases(corpus)
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
        if not ce_root: raise ValueError("--ce-root is required")
        ce_root = Path(ce_root).resolve()
        module = Path(ce_module).resolve() if ce_module else ce_root / "src/compute-engine/index.ts"
        tsx = ce_root / "node_modules/tsx/dist/loader.mjs"
        if not module.is_file() or ((not ce_module or rules) and not tsx.is_file()):
            raise ValueError("CE module and required tsx dependency are missing")
        command = [node, *(["--import", tsx.as_uri()] if not ce_module or rules else []), str(Path(__file__).parent / "adapters/ce.mjs")]
        env["CE_MODULE"] = str(module)
        if rules: env["CE_RULES_MODULE"] = str(ce_root / "src/integration-rules.ts")
        version = {"revision": subprocess.check_output(["git", "-C", str(ce_root), "rev-parse", "HEAD"], text=True).strip(),
                   "dirty": bool(subprocess.check_output(["git", "-C", str(ce_root), "status", "--porcelain"], text=True).strip()),
                   "rules": rules,
                   "runtime": subprocess.check_output([node, "--version"], text=True).strip()}
        if ce_module:
            import hashlib
            version["module_sha256"] = hashlib.sha256(module.read_bytes()).hexdigest()
            version["load_mode"] = "caller-built-bundle"
        else:
            version["load_mode"] = "source-tsx"
    else:
        if not external: raise ValueError("External engine requires --command-json with an executable argv array")
        command = json.loads(external)
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise ValueError("Command must be an argv array")
        version = {"command_digest": digest(command), "version": "adapter-reported-see-results"}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    metadata = {"schema_version": 1, "engine": engine + ("-rubi" if rules else ""),
                "engine_identity": version, "started_utc": datetime.now(timezone.utc).isoformat(),
                "platform": platform.system(), "architecture": platform.machine(),
                "python": platform.python_version(), "logical_cpus": os.cpu_count(),
                "timeout_seconds": timeout, "verification_timeout_seconds": verify_timeout,
                "jobs": jobs, "case_count": len(cases), "corpus_sha256": digest(load_cases(corpus)),
                "selected_ids": [c["id"] for c in cases], "selection_seed": seed,
                "isolation": "fresh process per case; wall budget includes startup and translation",
                "verifier": "SymPy 1.14.0", "independent_engine_verifier": engine != "sympy",
                "memory_limit": "not-enforced", "repeats": 1,
                "comparison_warning": "Pilot timings only; parallel contention and one repetition preclude performance rankings"}
    write_json(output / "run.json", metadata)

    def one(case):
        solver_case = {k: case[k] for k in SOLVER_FIELDS if k in case}
        result = invoke(command, {"protocol_version": 1, "case": solver_case}, timeout, env)
        if result.get("status") not in STATUSES | {"timeout", "launch-error", "process-error", "protocol-error"}:
            result = {"status": "protocol-error", "reason": "Unknown adapter status"}
        if result.get("status") == "answer" and "answer" not in result:
            result = {"status": "protocol-error", "reason": "Missing answer"}
        if result["status"] != "answer" and case["expected"]["status"] not in {"divergent", "undefined"}:
            verification = {"verdict": "not-solved", "wall_ms": 0}
        else:
            verification = invoke([sys.executable, "-m", "integral_benchmark.verifier"],
                                  {"case": case, "result": result}, verify_timeout)
        if "verdict" not in verification:
            verification["verdict"] = "verification-timeout" if verification.get("status") == "timeout" else "verifier-error"
        return {"id": case["id"], "family": case["family"], "kind": case["kind"],
                "case_sha256": digest(case), "result": result, "verification": verification}

    records = []
    # Append as cases finish: interrupted runs retain partial evidence and selected IDs.
    with (output / "results.jsonl").open("w", encoding="utf-8") as log:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(one, c): c["id"] for c in cases}
            for future in as_completed(futures):
                record = future.result()
                records.append(record)
                log.write(json.dumps(record, ensure_ascii=False) + "\n")
                log.flush()
                print(f"{len(records)}/{len(cases)} {record['id']} {record['result']['status']} {record['verification']['verdict']}", flush=True)
    metadata["finished_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["completed"] = len(records)
    write_json(output / "run.json", metadata)
    return records
