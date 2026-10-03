"""Original pilot fixtures, not transcriptions of contest or textbook collections."""

import json
from pathlib import Path
from .expressions import parse
from .model import validate


def build():
    cases = []

    def add(id, family, f, answer=None, bounds=None, status="finite", kind=None,
            domain="real", evidence="Elementary calculus identity; reference requires independent audit.",
            contour=None, points=None):
        kind = kind or ("contour" if contour else "definite" if bounds else "indefinite")
        v = "z" if contour else "x"
        c = {"schema_version": 1, "id": f"pilot:{id}", "kind": kind,
             "integrand": parse(f), "variable": v, "domains": {v: domain}, "assumptions": [],
             "assumptions_status": "explicit", "branches": "principal; indefinite identities on common differentiable domain",
             "family": family, "classification": "curated", "parameters": [],
             "source": {"suite": "original-pilot", "locator": id, "redistribution": "project-license"},
             "expected": {"status": status, "expression": parse(answer) if answer else None,
                          "trust": "curated-reference", "evidence": evidence},
             "sample_points": points or (["1/5", "1/3", "1/2", "2/3", "4/5"] if domain == "positive"
                                         else ["-4/5", "-1/2", "-1/5", "1/5", "1/2", "4/5"])}
        if bounds: c["bounds"] = [parse(x) for x in bounds]
        if contour: c["contour"] = contour
        cases.append(validate(c))

    indefinite = [
        ("polynomial", "rational-polynomial", "3*x**2+2*x+1", "x**3+x**2+x"),
        ("reciprocal", "rational-polynomial", "1/x", "log(Abs(x))"),
        ("lorentz", "rational-polynomial", "1/(1+x**2)", "atan(x)"),
        ("partial-fractions", "rational-polynomial", "1/(x**2-1)", "log(Abs((x-1)/(x+1)))/2"),
        ("repeated-pole", "rational-polynomial", "1/(1+x**2)**2", "x/(2*(1+x**2))+atan(x)/2"),
        ("sqrt", "algebraic-radicals", "sqrt(x)", "2*x**(3/2)/3"),
        ("semicircle", "algebraic-radicals", "sqrt(1-x**2)", "(x*sqrt(1-x**2)+asin(x))/2"),
        ("radical-substitution", "algebraic-radicals", "x/sqrt(1+x**2)", "sqrt(1+x**2)"),
        ("power-fraction", "algebraic-general", "x**(2/3)", "3*x**(5/3)/5"),
        ("exponential", "exponential", "exp(3*x)", "exp(3*x)/3"),
        ("exponential-parts", "exponential", "x*exp(x)", "(x-1)*exp(x)"),
        ("gaussian", "exponential", "exp(-x**2)", "sqrt(pi)*erf(x)/2"),
        ("logarithm", "logarithmic", "log(x)", "x*log(x)-x"),
        ("log-square", "logarithmic", "log(x)**2/x", "log(x)**3/3"),
        ("exp-log", "exponential-logarithmic", "exp(x)/(1+exp(x))", "log(1+exp(x))"),
        ("nested-exp", "exponential-logarithmic", "exp(x+exp(x))", "exp(exp(x))"),
        ("sin", "trigonometric", "sin(x)", "-cos(x)"),
        ("cos-square", "trigonometric", "cos(x)**2", "x/2+sin(2*x)/4"),
        ("trig-substitution", "trigonometric", "sin(x)*cos(x)**3", "-cos(x)**4/4"),
        ("arctan", "inverse-trigonometric", "atan(x)", "x*atan(x)-log(1+x**2)/2"),
        ("arcsin", "inverse-trigonometric", "asin(x)", "x*asin(x)+sqrt(1-x**2)"),
        ("sinh", "hyperbolic", "sinh(x)", "cosh(x)"),
        ("tanh", "hyperbolic", "tanh(x)", "log(cosh(x))"),
        ("asinh", "inverse-hyperbolic", "asinh(x)", "x*asinh(x)-sqrt(1+x**2)"),
        ("absolute", "piecewise-absolute", "Abs(x)", "x*Abs(x)/2"),
        ("erf", "special-other", "erf(x)", "x*erf(x)+exp(-x**2)/sqrt(pi)"),
        ("sinc", "special-other", "sin(x)/x", "Si(x)"),
        ("exp-integral", "special-other", "exp(x)/x", "Ei(x)"),
        ("polylog", "hypergeometric-polylog", "-log(1-x)/x", "polylog(2,x)"),
        ("elliptic", "elliptic", "1/sqrt(1-sin(x)**2/2)", "elliptic_f(x,1/2)"),
        ("bessel", "bessel", "besselj(1,x)", "-besselj(0,x)"),
        ("digamma", "gamma-beta-zeta", "polygamma(0,x)", "log(gamma(x))"),
    ]
    positive = {"sqrt", "power-fraction", "logarithm", "log-square", "exp-integral", "digamma"}
    for id, family, f, answer in indefinite:
        add(id, family, f, answer, domain="positive" if id in positive else "real")
    definite = [
        ("poly-finite", "rational-polynomial", "x**4", "2/5", ("-1", "1")),
        ("trig-finite", "trigonometric", "sin(x)", "2", ("0", "pi")),
        ("odd-symmetry", "definite-symmetry", "x*exp(-x**2)", "0", ("-2", "2")),
        ("reflection", "definite-symmetry", "x*sin(x)", "pi", ("0", "pi")),
        ("abs-finite", "piecewise-absolute", "Abs(x)", "1", ("-1", "1")),
        ("floor-finite", "piecewise-discrete", "floor(x)", "3", ("0", "3")),
        ("endpoint-sqrt", "improper-endpoints", "1/sqrt(x)", "2", ("0", "1")),
        ("endpoint-log", "improper-endpoints", "log(x)", "-1", ("0", "1")),
        ("lorentz-line", "improper-infinity", "1/(1+x**2)", "pi", ("-oo", "oo")),
        ("gaussian-line", "improper-infinity", "exp(-x**2)", "sqrt(pi)", ("-oo", "oo")),
        ("gaussian-half", "improper-infinity", "exp(-x**2)", "sqrt(pi)/2", ("0", "oo")),
        ("sinc-half", "improper-infinity", "sin(x)/x", "pi/2", ("0", "oo")),
        ("fourier-lorentz", "improper-infinity", "cos(x)/(1+x**2)", "pi/exp(1)", ("-oo", "oo")),
        ("quartic-line", "improper-infinity", "1/(1+x**4)", "pi/sqrt(2)", ("-oo", "oo")),
        ("gamma-moment", "gamma-beta-zeta", "x**3*exp(-x)", "6", ("0", "oo")),
        ("beta-half", "gamma-beta-zeta", "1/sqrt(x*(1-x))", "pi", ("0", "1")),
        ("zeta-moment", "gamma-beta-zeta", "x/(exp(x)-1)", "pi**2/6", ("0", "oo")),
        ("dilog-value", "hypergeometric-polylog", "-log(1-x)/x", "pi**2/6", ("0", "1")),
        ("elliptic-complete", "elliptic", "1/sqrt(1-sin(x)**2/2)", "elliptic_k(1/2)", ("0", "pi/2")),
    ]
    for id, family, f, answer, bounds in definite:
        add(id, family, f, answer, bounds, evidence="Standard exact identity; compare independent CAS result with reference, not a formal proof.")
    for id, f, bounds in [
        ("cubic-cos-divergence", "cos(x)/(x**3+1)", ("-oo", "oo")),
        ("interior-pole", "1/x", ("-1", "1")),
        ("even-pole", "1/x**2", ("-1", "1")),
        ("endpoint-pole", "1/x", ("0", "1")),
        ("tail-divergence", "1/(1+x)", ("0", "oo")),
    ]:
        add(id, "improper-endpoints" if id != "tail-divergence" else "improper-infinity",
            f, bounds=bounds, status="divergent",
            evidence="A one-sided integral at a pole or the logarithmic tail fails to have a finite limit.")
    add("pv-simple", "principal-value", "1/x", "0", ("-1", "1"), kind="principal-value",
        evidence="Symmetric exclusion around zero cancels exactly.")
    add("pv-cos-cubic", "principal-value", "cos(x)/(x**3+1)",
        "pi*(sin(1)+exp(-sqrt(3)/2)*(sin(1/2)+sqrt(3)*cos(1/2)))/3",
        ("-oo", "oo"), kind="principal-value", evidence="Upper exponential kernel residue plus the simple real pole half residue, then real projection.")
    add("pv-double-diverges", "principal-value", "1/x**2", bounds=("-1", "1"),
        kind="principal-value", status="divergent", evidence="The symmetrically truncated integral grows as 2/epsilon.")
    circle = {"kind": "circle", "center": 0, "radius": 2, "orientation": "counterclockwise"}
    for id, f, answer, changes, status in [
        ("circle-no-poles", "z**2", "0", {}, "finite"),
        ("circle-one", "1/z", "2*pi*I", {}, "finite"),
        ("circle-multiple", "1/z+2/(z-1)", "6*pi*I", {}, "finite"),
        ("circle-outside", "1/(z-3)", "0", {}, "finite"),
        ("circle-clockwise", "1/z", "-2*pi*I", {"orientation": "clockwise"}, "finite"),
        ("circle-boundary", "1/(z-2)", None, {}, "undefined"),
        ("circle-double", "1/z**2", "0", {}, "finite"),
        ("circle-essential", "exp(1/z)", "2*pi*I", {}, "finite"),
        ("circle-essential-times", "z*exp(1/z)", "pi*I", {}, "finite"),
    ]:
        add(id, "contour-essential" if "essential" in id else "contour-meromorphic",
            f, answer, status=status, domain="complex", contour={**circle, **changes},
            evidence="Residue theorem with explicit circular containment and orientation; boundary pole is undefined without a prescription.")
    return cases


def write(path):
    cases = build()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8")
    return len(cases)
