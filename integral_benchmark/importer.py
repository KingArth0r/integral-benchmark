"""Reproducible inventory and opt-in imports of a pinned upstream checkout."""

from collections import Counter, defaultdict
import json
from pathlib import Path
import subprocess
from .expressions import parse, TranslationError, symbols
from .model import digest, infer_family, semantic_key, validate, write_json

SUITES = ("rubi", "independent", "hebisch", "blake", "mit_bee", "mit_bee_official")
REDISTRIBUTION = {"rubi": "upstream-MIT", "independent": "upstream-MIT",
                  "blake": "permission-review", "hebisch": "permission-review",
                  "mit_bee": "permission-review", "mit_bee_official": "unlicensed-source-review"}


def convert(row, suite, path, revision):
    expr = parse(row["integrand"])
    definite = "lower" in row and "upper" in row
    kind = "definite" if definite else "indefinite"
    answer_text = row.get("value" if definite else "integral")
    answer_error = None
    try:
        answer = parse(answer_text) if answer_text is not None else None
    except TranslationError as exc:
        answer, answer_error = None, str(exc)
    family = infer_family(expr, kind)
    if suite == "blake": family = "algebraic-pseudoelliptic"
    if suite == "hebisch": family = "exponential-logarithmic"
    variable = row.get("variable", "x")
    case = {
        "schema_version": 1,
        "id": f"{suite}:{digest([path, row.get('index'), row.get('source')])[:20]}",
        "kind": kind, "integrand": expr, "variable": variable,
        "domains": {}, "assumptions": [], "assumptions_status": "not-specified-upstream",
        "branches": "principal-complex-unless-source-says-otherwise-review-required",
        "family": family, "classification": "heuristic-syntax-not-method",
        "parameters": sorted(set(symbols(expr)) - {variable}),
        "source": {"suite": suite, "url": "https://github.com/sympy/integration-test-suites",
                   "revision": revision, "file": path, "locator": row.get("source"),
                   "index": row.get("index"), "record_sha256": digest(row),
                   "redistribution": REDISTRIBUTION[suite]},
        "expected": {"status": "unknown", "expression": answer,
                     "trust": "upstream-unreviewed", "translation_error": answer_error},
    }
    if definite: case["bounds"] = [parse(row["lower"]), parse(row["upper"])]
    return validate(case)


def scan(upstream, output, import_suites=(), include_review=False):
    upstream, output = Path(upstream), Path(output)
    revision = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain"], text=True).strip()
    if dirty: raise ValueError("Upstream checkout is dirty; inventory must identify immutable source data")
    if set(import_suites) - set(SUITES): raise ValueError("Unknown suite")
    if not include_review and any(REDISTRIBUTION[s] != "upstream-MIT" for s in import_suites):
        raise ValueError("Use --include-review for local-only imports with unresolved source permissions")
    suite_stats, family_stats = {}, defaultdict(Counter)
    duplicate_groups = defaultdict(list)
    errors, manifests = [], []
    imports = output / "imported"
    if import_suites: imports.mkdir(parents=True, exist_ok=True)
    for suite in SUITES:
        counts = Counter()
        destination = (imports / f"{suite}.jsonl").open("w", encoding="utf-8") if suite in import_suites else None
        try:
            for file in sorted((upstream / "data" / suite).rglob("*.jsonl")):
                rel = file.relative_to(upstream).as_posix()
                content = file.read_bytes()
                import hashlib
                manifests.append({"file": rel, "sha256": hashlib.sha256(content).hexdigest()})
                for lineno, line in enumerate(content.decode("utf-8").splitlines(), 1):
                    if not line.strip(): continue
                    row = json.loads(line)
                    counts["records"] += 1
                    counts["definite" if "lower" in row else "indefinite"] += 1
                    counts["reference_present" if row.get("integral") is not None or row.get("value") is not None else "reference_missing"] += 1
                    try:
                        case = convert(row, suite, rel, revision)
                        counts["translated"] += 1
                        counts["parameterized" if case["parameters"] else "concrete"] += 1
                        family_stats[case["family"]]["inventory_records"] += 1
                        family_stats[case["family"]][case["kind"]] += 1
                        duplicate_groups[semantic_key(case)].append(case["id"])
                        if case["expected"]["translation_error"]:
                            counts["reference_translation_failed"] += 1
                        if destination:
                            destination.write(json.dumps(case, ensure_ascii=False) + "\n")
                    except (TranslationError, ValueError, RecursionError) as exc:
                        counts["translation_failed"] += 1
                        errors.append({"suite": suite, "file": rel, "line": lineno, "index": row.get("index"), "reason": str(exc)[:300]})
        finally:
            if destination: destination.close()
        suite_stats[suite] = {**counts, "redistribution": REDISTRIBUTION[suite]}
    report = {
        "schema_version": 1, "upstream": "https://github.com/sympy/integration-test-suites",
        "revision": revision, "suites": suite_stats, "families": dict(family_stats),
        "raw_records": sum(s["records"] for s in suite_stats.values()),
        "translated_unique_structural_cases": len(duplicate_groups),
        "duplicate_records": sum(len(g) - 1 for g in duplicate_groups.values()),
        "deduplication": "alpha-renamed variable; identical trees and semantics only; not algebraic equivalence",
        "assumptions": "Upstream assumptions are not reconstructed; imported references are unreviewed.",
        "manifest": manifests, "translation_failures": errors,
        "duplicates": {k: v for k, v in duplicate_groups.items() if len(v) > 1},
        "imported_suites": list(import_suites),
    }
    write_json(output / "inventory.json", report)
    return report
