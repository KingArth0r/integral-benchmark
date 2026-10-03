"""One JSON request per process. No expected answer is supplied to solvers."""

import json
import sys
import time
import sympy as s
from .expressions import to_sympy, from_sympy, TranslationError


def solve(case):
    if case["assumptions"]:
        return {"status": "unsupported-assumptions"}
    if case["kind"] in {"contour", "numerical"}:
        return {"status": "unsupported-kind", "reason": "Adapter does not implement this entry point"}
    domains = case["domains"]
    try:
        f = to_sympy(case["integrand"], domains)
        x = to_sympy(case["variable"], domains)
        bounds = [to_sympy(a, domains) for a in case.get("bounds", [])]
    except (TranslationError, TypeError, ValueError) as exc:
        return {"status": "translation-error", "reason": str(exc)}
    start = time.perf_counter()
    if case["kind"] == "indefinite":
        result = s.integrate(f, x)
    elif case["kind"] == "principal-value":
        result = s.Integral(f, (x, *bounds)).principal_value()
    else:
        result = s.integrate(f, (x, *bounds))
    elapsed = (time.perf_counter() - start) * 1000
    record = {"solver_ms": elapsed, "answer_text": str(result), "engine_version": s.__version__}
    if result.has(s.Integral): return {**record, "status": "unevaluated"}
    if result.has(s.Piecewise): return {**record, "status": "conditional", "reason": "Conditional answer not yet exported by adapter"}
    if result in (s.oo, -s.oo) or result.has(s.AccumBounds):
        return {**record, "status": "divergent"}
    if result in (s.nan, s.zoo): return {**record, "status": "undefined"}
    try:
        return {**record, "status": "answer", "answer": from_sympy(result)}
    except TranslationError as exc:
        return {**record, "status": "answer-untranslated", "reason": str(exc)}


if __name__ == "__main__":
    try:
        request = json.load(sys.stdin)
        result = solve(request["case"])
    except Exception as exc:
        result = {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, allow_nan=False))
