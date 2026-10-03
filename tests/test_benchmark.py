import json
from pathlib import Path
import sys
import tempfile
import unittest

from integral_benchmark.expressions import parse, to_sympy, from_sympy, TranslationError
from integral_benchmark.importer import convert
from integral_benchmark.model import semantic_key, validate
from integral_benchmark.seed import build
from integral_benchmark.runner import invoke, SOLVER_FIELDS
from integral_benchmark.verifier import verify
from integral_benchmark.report import generate


class Expressions(unittest.TestCase):
    def test_exact_rational(self):
        import sympy as s
        self.assertEqual(to_sympy(parse("1/3")), s.Rational(1, 3))
        self.assertEqual(to_sympy(parse("0.1")), s.Rational(1, 10))
        self.assertEqual(to_sympy(parse("ln(x)")), to_sympy(parse("log(x)")))

    def test_no_code_execution(self):
        for text in ["__import__('os').system('x')", "x.__class__", "[x for x in y]",
                     "lambda x: x", "open('a')", "sin(x, evil=1)", "x[0]"]:
            with self.subTest(text=text), self.assertRaises(TranslationError): parse(text)

    def test_roundtrip(self):
        for text in ["sin(x)/3", "pi*I", "exp(-x**2)", "elliptic_f(x,1/2)", "-oo", "re(x)", "im(x)"]:
            expr = to_sympy(parse(text))
            self.assertEqual(to_sympy(from_sympy(expr)), expr)

    def test_complex_projection(self):
        import sympy as s
        self.assertEqual(to_sympy(["Imaginary", ["Multiply", "ImaginaryUnit", "Pi"]]), s.pi)

    def test_unknown_operator_is_not_a_silent_function(self):
        with self.assertRaises(TranslationError): to_sympy(["ArbitraryCode", "x"])


class Cases(unittest.TestCase):
    def test_seed_valid_unique(self):
        cases = build()
        self.assertGreaterEqual(len(cases), 60)
        self.assertEqual(len(cases), len({c["id"] for c in cases}))
        for case in cases: validate(case)

    def test_domains_are_part_of_identity(self):
        a = build()[0]
        b = {**a, "domains": {"x": "positive"}}
        self.assertNotEqual(semantic_key(a), semantic_key(b))

    def test_invalid_domain_rejected(self):
        with self.assertRaises(ValueError): validate({**build()[0], "domains": {"x": "pretend-real"}})

    def test_pv_not_deduplicated_with_ordinary(self):
        a = next(c for c in build() if c["id"] == "pilot:interior-pole")
        b = {**a, "kind": "principal-value"}
        self.assertNotEqual(semantic_key(a), semantic_key(b))

    def test_alpha_rename(self):
        a = build()[0]
        b = json.loads(json.dumps(a).replace('"x"', '"t"'))
        self.assertEqual(semantic_key(a), semantic_key(b))

    def test_input_has_no_solution(self):
        case = build()[0]
        supplied = {k: case[k] for k in SOLVER_FIELDS if k in case}
        self.assertNotIn("expected", supplied)
        self.assertNotIn("sample_points", supplied)
        self.assertNotIn("family", supplied)

    def test_import_does_not_invent_conditions(self):
        row = {"index": 1, "integrand": "x**a", "integral": "x**(a+1)/(a+1)", "variable": "x"}
        case = convert(row, "rubi", "data/a.jsonl", "test")
        self.assertEqual(case["expected"]["trust"], "upstream-unreviewed")
        self.assertEqual(case["parameters"], ["a"])
        self.assertEqual(case["assumptions_status"], "not-specified-upstream")

    def test_import_preserves_problem_without_reference(self):
        row = {"index": 1, "integrand": "x", "integral": "Unsupported(x)", "variable": "x"}
        case = convert(row, "rubi", "data/a.jsonl", "test")
        self.assertIsNone(case["expected"]["expression"])
        self.assertTrue(case["expected"]["translation_error"])


class Verification(unittest.TestCase):
    def case(self, name): return next(c for c in build() if c["id"] == f"pilot:{name}")

    def test_additive_constant(self):
        result = {"status": "answer", "answer": parse("x**3+x**2+x+7")}
        self.assertEqual(verify(self.case("polynomial"), result)["verdict"], "identity-checked")

    def test_wrong_answer(self):
        result = {"status": "answer", "answer": parse("x")}
        self.assertEqual(verify(self.case("polynomial"), result)["verdict"], "numeric-mismatch")

    def test_no_finite_value_for_divergence(self):
        self.assertEqual(verify(self.case("cubic-cos-divergence"), {"status": "answer", "answer": 0})["verdict"], "wrong")

    def test_nan_is_not_divergence_proof(self):
        self.assertEqual(verify(self.case("cubic-cos-divergence"), {"status": "undefined"})["verdict"], "safe-rejection")

    def test_reference_not_called_proof(self):
        case = self.case("gaussian-line")
        result = {"status": "answer", "answer": case["expected"]["expression"]}
        self.assertEqual(verify(case, result)["verdict"], "reference-match")
        case["expected"]["trust"] = "upstream-unreviewed"
        self.assertEqual(verify(case, result)["verdict"], "reference-match-unreviewed")

    def test_no_fallback_pv(self):
        self.assertEqual(verify(self.case("interior-pole"), {"status": "answer", "answer": 0})["verdict"], "wrong")
        self.assertEqual(verify(self.case("pv-simple"), {"status": "answer", "answer": 0})["verdict"], "reference-match")


class Processes(unittest.TestCase):
    def test_timeout(self):
        r = invoke([sys.executable, "-c", "import time; time.sleep(10)"], {}, .15)
        self.assertEqual(r["status"], "timeout")
        self.assertLess(r["wall_ms"], 3000)

    def test_protocol_error(self):
        r = invoke([sys.executable, "-c", "print('not JSON')"], {}, 5)
        self.assertEqual(r["status"], "protocol-error")

    def test_child_error(self):
        r = invoke([sys.executable, "-c", "raise ValueError('failure')"], {}, 5)
        self.assertEqual(r["status"], "process-error")


class Reports(unittest.TestCase):
    def test_recheck_keeps_solver_evidence(self):
        from integral_benchmark.seed import write
        from integral_benchmark.model import digest
        from integral_benchmark.recheck import recheck
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "cases.jsonl")
            case = build()[0]
            run = root / "run"
            run.mkdir()
            result = {"status": "answer", "answer": case["expected"]["expression"], "solver_ms": 123}
            original = {"id": case["id"], "case_sha256": digest(case), "result": result,
                        "verification": {"verdict": "unverified"}}
            (run / "run.json").write_text("{}")
            (run / "results.jsonl").write_text(json.dumps(original))
            recheck(root / "cases.jsonl", run, root / "checked", timeout=10)
            checked = json.loads((root / "checked/results.jsonl").read_text())
            self.assertEqual(checked["result"], result)
            self.assertEqual(checked["verification"]["verdict"], "identity-checked")
            self.assertEqual(json.loads((run / "results.jsonl").read_text()), original)
            with self.assertRaises(ValueError): recheck(root / "cases.jsonl", run, run)

    def test_unmeasured_families_remain(self):
        from integral_benchmark.seed import write
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "cases.jsonl")
            report = generate(root / "cases.jsonl", None, [], root)
            self.assertEqual(len(report["families"]), 30)
            self.assertTrue(any(r["pilot_cases"] == 0 for r in report["families"]))
            self.assertTrue((root / "COVERAGE.md").is_file())

    def test_unsupported_stays_in_denominator(self):
        from integral_benchmark.seed import write
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write(root / "cases.jsonl")
            run = root / "run"
            run.mkdir()
            metadata = {"engine": "fake", "engine_identity": {}, "timeout_seconds": 1,
                        "verification_timeout_seconds": 1, "jobs": 1, "independent_engine_verifier": True}
            (run / "run.json").write_text(json.dumps(metadata))
            records = [{"family": "rational-polynomial", "result": {"status": "unsupported-kind"},
                        "verification": {"verdict": "not-solved"}},
                       {"family": "rational-polynomial", "result": {"status": "answer"},
                        "verification": {"verdict": "identity-checked"}}]
            (run / "results.jsonl").write_text("\n".join(json.dumps(r) for r in records))
            report = generate(root / "cases.jsonl", None, [run], root)
            counts = report["runs"]["fake"]["families"]["rational-polynomial"]
            self.assertEqual(counts["attempted"], 2)
            self.assertEqual(counts["identity-checked"], 1)


if __name__ == "__main__": unittest.main()
