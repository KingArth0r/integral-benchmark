"""Recheck stored solver answers without rerunning or modifying the solver evidence."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from .model import load_cases, digest, write_json
from .runner import invoke


def recheck(corpus, input_run, output, ids=(), timeout=20):
    source, destination = Path(input_run).resolve(), Path(output).resolve()
    if source == destination: raise ValueError("Rechecks must preserve the original run in a different directory")
    cases = {c["id"]: c for c in load_cases(corpus)}
    metadata = json.loads((source / "run.json").read_text())
    records = [json.loads(line) for line in (source / "results.jsonl").read_text().splitlines() if line.strip()]
    if set(ids) - {r["id"] for r in records}: raise ValueError("Unknown recheck IDs")
    original_digest = digest(records)
    changed = []
    for record in records:
        case = cases.get(record["id"])
        if case is None or digest(case) != record["case_sha256"]: raise ValueError("Case changed since solver run")
        if ids and record["id"] not in ids: continue
        previous = record["verification"]
        verification = invoke([sys.executable, "-m", "integral_benchmark.verifier"],
                              {"case": case, "result": record["result"]}, timeout)
        if "verdict" not in verification:
            verification["verdict"] = "verification-timeout" if verification.get("status") == "timeout" else "verifier-error"
        record["verification"] = verification
        changed.append({"id": record["id"], "previous_verification": previous})
    metadata["recheck"] = {"at_utc": datetime.now(timezone.utc).isoformat(), "input_results_sha256": original_digest,
                           "verification_timeout_seconds": timeout, "previous_evidence": changed,
                           "note": "Solver answers and timings unchanged; only selected verification rerun"}
    write_json(destination / "run.json", metadata)
    (destination / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
