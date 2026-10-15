"""Conservative evidence labels; an equality check is not a convergence proof."""

import json
import sys
import sympy as s
from .expressions import to_sympy, TranslationError, symbols, parse
from .assumptions import context


def verify(case, result):
    expected = case["expected"]
    status = result["status"]
    if status == 'conditional':
        return {'verdict': 'conditional-unverified',
                'detail': 'Returned conditions retained; domain implication/completeness not certified'}
    if expected["status"] in {"divergent", "undefined"}:
        if status == expected["status"]:
            return {"verdict": "classification-match", "detail": "Matches curated semantic classification, not a solver proof"}
        if status == "answer":
            return {"verdict": "wrong", "detail": "Finite answer contradicts the specified integral semantics"}
        # NaN/undefined is safe rejection, but does not specifically prove divergence.
        if status == "undefined" and expected["status"] == "divergent":
            return {"verdict": "safe-rejection", "detail": "No finite answer, but divergence not explicitly classified"}
        return {"verdict": "not-solved"}
    if status != "answer": return {"verdict": "not-solved"}
    try:
        domains, condition = context(case)
        obligations = list(result.get('input_branch_warnings', []))
        answer = to_sympy(result["answer"], domains, obligations)
        if case["kind"] == "indefinite":
            f = to_sympy(case["integrand"], domains)
            x = to_sympy(case["variable"], domains)
            residual = s.diff(answer, x) - f
        elif expected.get("expression") is not None:
            residual = answer - to_sympy(expected["expression"], domains)
        else:
            return {"verdict": "unverified", "detail": "No reference for definite result"}
        if residual.has(s.nan, s.zoo, s.oo, -s.oo):
            return {"verdict": "unverified", "detail": "Nonfinite residual"}
        exact = s.simplify(residual)
        if exact == 0:
            if obligations:
                return {'verdict': 'identity-checked-restricted' if case['kind'] == 'indefinite' else 'unverified',
                        'branch_obligations': obligations,
                        'detail': 'Local principal-branch comparison only; not full-domain correctness'}
            if case["kind"] == "indefinite":
                return {"verdict": "identity-checked", "detail": "Derivative identity on common differentiable domain; global branch/domain completeness not certified",
                        'assumptions_status': case.get('assumptions_status', 'explicit-case-contract'),
                        'parameter_completeness': 'not-certified' if case.get('parameters') else 'not-applicable'}
            return {"verdict": "reference-match" if expected["trust"] == "curated-reference" else "reference-match-unreviewed",
                    "detail": "Exact equality to reference; convergence and reference validity are separate obligations"}
        if obligations:
            return {'verdict': 'unverified', 'branch_obligations': obligations,
                    'detail': 'Branch-restricted symbolic comparison unresolved; no unrestricted sampling'}
        if case.get("parameters") or (case["kind"] == "indefinite" and set(symbols(case["integrand"])) - {case["variable"]}):
            return {"verdict": "unverified", "detail": "Parameterized residual not symbolically resolved; no arbitrary parameter sampling"}
        points = case.get("sample_points", []) if case["kind"] == "indefinite" else [None]
        if not points: return {"verdict": "unverified", "detail": "No domain-reviewed sample points"}
        checked, failures = 0, []
        for point in points:
            if point is not None and condition.subs(x, to_sympy(parse(point))) is not s.true:
                continue
            r = residual if point is None else residual.subs(x, to_sympy(parse(point)))
            if r.free_symbols: continue
            values = []
            for precision in (40, 70):
                n = s.N(r, precision)
                if n.has(s.nan, s.zoo, s.oo, -s.oo): break
                try: values.append(abs(complex(n)))
                except (TypeError, ValueError, OverflowError): break
            if len(values) != 2: continue
            checked += 1
            if min(values) > 1e-15: failures.append({"point": point, "residual_magnitudes": values})
            elif max(values) > 1e-25:
                return {"verdict": "unverified", "detail": "Residual near numerical decision threshold"}
        if failures:
            return {"verdict": "numeric-mismatch", "counterexamples": failures,
                    "detail": "Needs domain/reference review; not automatically a proven solver error"}
        if checked >= (4 if case["kind"] == "indefinite" else 1):
            return {"verdict": "numerically-supported", "points_checked": checked,
                    "detail": "Sampling only; not a proof"}
        return {"verdict": "unverified", "points_checked": checked}
    except (TranslationError, ValueError, TypeError, NotImplementedError) as exc:
        return {"verdict": "unverified", "detail": str(exc)}


if __name__ == "__main__":
    try:
        request = json.load(sys.stdin)
        response = verify(request["case"], request["result"])
    except Exception as exc:
        response = {"verdict": "verifier-error", "detail": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(response, allow_nan=False))
