"""Coverage denominators retain missing families and unsuccessful outcomes."""

from collections import Counter, defaultdict
import json
from pathlib import Path
from .model import ROOT, load_cases, write_json


def generate(corpus, inventory, runs, output):
    cases = load_cases(corpus)
    taxonomy = json.loads(Path(__file__).with_name("taxonomy.json").read_text())
    inventory = json.loads(Path(inventory).read_text()) if inventory else {}
    results = {}
    for run in runs:
        p = Path(run)
        meta = json.loads((p / "run.json").read_text())
        records = [json.loads(x) for x in (p / "results.jsonl").read_text().splitlines() if x.strip()]
        key = meta["engine"]
        if key in results: raise ValueError("Use distinct engine labels; repeated runs need a separate comparison report")
        by_family = defaultdict(Counter)
        for r in records:
            counts = by_family[r["family"]]
            counts["attempted"] += 1
            counts[r["verification"]["verdict"]] += 1
            counts["solver:" + r["result"]["status"]] += 1
        results[key] = {"metadata": meta, "families": dict(by_family),
                        "verdicts": dict(Counter(r["verification"]["verdict"] for r in records)),
                        "statuses": dict(Counter(r["result"]["status"] for r in records)),
                        "follow_up": [{"id": r.get("id", "unknown"), "family": r["family"],
                                       "solver_status": r["result"]["status"],
                                       "verdict": r["verification"]["verdict"]}
                                      for r in records if r["verification"]["verdict"] not in
                                      {"identity-checked", "reference-match", "classification-match"}]}
    curated = Counter(c["family"] for c in cases)
    rows = []
    semantic_families = {"definite-symmetry", "improper-endpoints", "improper-infinity", "principal-value",
                         "contour-meromorphic", "contour-essential", "contour-branch", "parameter-conditions",
                         "series-products", "non-elementarity", "multivariate", "numerical"}
    for family in taxonomy:
        id = family["id"]
        rows.append({**family, "pilot_cases": curated[id],
                     "inventory_records": None if id in semantic_families else inventory.get("families", {}).get(id, {}).get("inventory_records", 0),
                     "engines": {key: value["families"].get(id, {}) for key, value in results.items()}})
    report = {"schema_version": 1, "title": "Integral Benchmark coverage map",
              "families": rows, "runs": results, "inventory_revision": inventory.get("revision"),
              "scope": "Single-variable pilot. Broader taxonomy rows are targets, not implemented coverage."}
    output = Path(output)
    write_json(output / "coverage.json", report)
    lines = ["# Integral Benchmark coverage map", "",
             "This map separates source inventory, runnable pilot coverage, and observed solver outcomes. "
             "It is not a ranking of overall CAS capability. Zero cases means an unmeasured gap, not solver failure.", "",
             "## Source inventory", "",
             f"Pinned upstream revision: `{inventory.get('revision', 'not inventoried')}`. "
             f"Raw records: {inventory.get('raw_records', 0):,}. "
             f"Structurally unique translated problems: {inventory.get('translated_unique_structural_cases', 0):,}. "
             f"Duplicate records among translated problems: {inventory.get('duplicate_records', 0):,}.", "",
             "Counts below classify integrand syntax, not the functions appearing in answers or required solution methods. "
             "Semantic families are marked Not classified because the inventory does not yet infer those properties. "
             "Imported assumptions and reference answers need further review.", "",
             "| Suite | Raw | Definite | Translation failures | Redistribution status |",
             "|---|---:|---:|---:|---|"]
    for name, counts in inventory.get("suites", {}).items():
        lines.append(f"| {name} | {counts['records']:,} | {counts.get('definite', 0):,} | {counts.get('translation_failed', 0):,} | {counts['redistribution']} |")
    lines += ["", "## Measured family coverage", "",
              "Each engine cell is **checked / attempted**. Checked means a derivative identity, "
              "equality to a curated reference, or an explicit classification match. These are different "
              "evidence levels, not formal global proofs. Numerical support and safe rejection are reported "
              "separately below and excluded from this count. All attempted cases remain in the denominator.", "",
              "| Family | Inventory records | Pilot cases | " + " | ".join(results) + " |",
              "|---|---:|---:|" + "---:|" * len(results)]
    checked_types = ("identity-checked", "reference-match", "classification-match")
    for row in rows:
        cells = []
        for engine in results:
            c = row["engines"][engine]
            cells.append(f"{sum(c.get(k, 0) for k in checked_types)} / {c.get('attempted', 0)}" if c else "Not measured")
        inventory_count = f"{row['inventory_records']:,}" if row['inventory_records'] is not None else "Not classified"
        lines.append(f"| {row['label']} | {inventory_count} | {row['pilot_cases']} | " + " | ".join(cells) + " |")
    lines += ["", "## Evidence and failure breakdown", ""]
    for engine, result in results.items():
        lines += [f"### {engine}", "", "| Verdict | Cases |", "|---|---:|"]
        for verdict, count in sorted(result["verdicts"].items()): lines.append(f"| {verdict} | {count} |")
        lines += ["", "| Solver or adapter outcome | Cases |", "|---|---:|"]
        for status, count in sorted(result["statuses"].items()): lines.append(f"| {status} | {count} |")
        m = result["metadata"]
        lines += ["", f"Engine identity: `{json.dumps(m['engine_identity'], sort_keys=True)}`. "
                  f"Budget {m['timeout_seconds']} seconds per fresh solver process, "
                  f"{m['verification_timeout_seconds']} seconds per verifier; {m['jobs']} parallel jobs. "
                  f"Verifier independent of solver engine: {m['independent_engine_verifier']}.", ""]
        lines += ["Cases requiring follow-up are not automatically solver bugs. An unsupported kind "
                  "can be an adapter limitation, and a numerical-only check can be a verifier limitation.", "",
                  "| Case | Solver outcome | Verification |", "|---|---|---|"]
        for item in result["follow_up"]:
            lines.append(f"| {item['id']} | {item['solver_status']} | {item['verdict']} |")
        lines.append("")
    lines += ["## Next coverage targets", "",
              "1. Audit parameter domains and branches before treating the large imported corpus as a gold set.",
              "2. Add source-reviewed Berkeley, HMMT, and JEE cases; retain exact year, round, and problem identifiers.",
              "3. Expand definite integrals, parameter boundaries, divergent near-misses, and branch-cut contours.",
              "4. Add numerical, non-elementarity, infinite-series, and multivariate protocols before scoring those tracks.",
              "5. Add tested adapters for Wolfram, Maple, Maxima, FriCAS, and Sage with explicit backend identities.",
              "6. Add domain-completeness certificates and independent reference audits; preserve inconclusive verdicts.",
              "7. Run paired, repeated, serial performance trials before publishing speed comparisons.", "",
              "The pilot is intentionally small and publicly visible. No contamination-resistant holdout exists yet. "
              "Case data and verification budgets are versioned; increasing either can change the map.", ""]
    (output / "COVERAGE.md").write_text("\n".join(lines), encoding="utf-8")
    return report
