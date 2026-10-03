import argparse
import json
from .model import ROOT


def main():
    parser = argparse.ArgumentParser(description="Integral Benchmark")
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("seed", help="Regenerate the original curated pilot")
    seed.add_argument("--output", default="corpus/pilot.jsonl")
    inventory = commands.add_parser("inventory", help="Audit a local clean upstream checkout")
    inventory.add_argument("--upstream", required=True)
    inventory.add_argument("--output", default="reports/inventory")
    inventory.add_argument("--import-suite", action="append", default=[])
    inventory.add_argument("--include-review", action="store_true")
    run = commands.add_parser("run", help="Run a solver and verify answers independently")
    run.add_argument("--corpus", default="corpus/pilot.jsonl")
    run.add_argument("--output", required=True)
    run.add_argument("--engine", required=True)
    run.add_argument("--timeout", type=float, default=10)
    run.add_argument("--verify-timeout", type=float, default=5)
    run.add_argument("--jobs", type=int, default=1)
    run.add_argument("--limit", type=int)
    run.add_argument("--seed", type=int, default=20261003)
    run.add_argument("--ce-root")
    run.add_argument("--ce-module", help="Fresh ESM bundle built from the recorded CE checkout")
    run.add_argument("--node", default="node")
    run.add_argument("--rules", action="store_true")
    run.add_argument("--command-json")
    report = commands.add_parser("report", help="Build a coverage map including unmeasured families")
    report.add_argument("--corpus", default="corpus/pilot.jsonl")
    report.add_argument("--inventory")
    report.add_argument("--run", action="append", default=[])
    report.add_argument("--output", default="reports")
    check = commands.add_parser("recheck", help="Recheck stored answers while preserving original solver evidence")
    check.add_argument("--corpus", default="corpus/pilot.jsonl")
    check.add_argument("--input-run", required=True)
    check.add_argument("--output", required=True)
    check.add_argument("--id", action="append", default=[])
    check.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args()
    if args.command == "seed":
        from .seed import write
        print(f"Wrote {write(args.output)} pilot cases")
    elif args.command == "inventory":
        from .importer import scan
        result = scan(args.upstream, args.output, args.import_suite, args.include_review)
        print(json.dumps({k: result[k] for k in ("revision", "raw_records", "translated_unique_structural_cases", "duplicate_records", "suites")}, indent=2))
    elif args.command == "run":
        if args.jobs < 1 or args.timeout <= 0 or args.verify_timeout <= 0 or (args.limit is not None and args.limit < 1):
            parser.error("Budgets, jobs, and limits must be positive")
        from .runner import run
        run(args.corpus, args.output, args.engine, args.timeout, args.verify_timeout,
            args.jobs, args.limit, args.ce_root, args.node, args.command_json, args.rules, args.seed, args.ce_module)
    elif args.command == "report":
        from .report import generate
        generate(args.corpus, args.inventory, args.run, args.output)
    elif args.command == "recheck":
        if args.timeout <= 0: parser.error("Timeout must be positive")
        from .recheck import recheck
        recheck(args.corpus, args.input_run, args.output, args.id, args.timeout)


if __name__ == "__main__":
    main()
