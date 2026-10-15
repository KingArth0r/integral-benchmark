"""Case validation and semantic identity without a solver dependency."""

import hashlib
import json
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from .expressions import heads

ROOT = Path(__file__).resolve().parents[1]
KINDS = {"indefinite", "definite", "principal-value", "contour", "numerical"}
STATES = {"finite", "divergent", "undefined", "unknown"}


@lru_cache(maxsize=1)
def family_ids():
    return {x["id"] for x in json.loads(Path(__file__).with_name("taxonomy.json").read_text())}


def validate(case):
    required = {"id", "kind", "integrand", "variable", "domains", "assumptions",
                "family", "source", "expected", "schema_version"}
    missing = required - case.keys()
    if missing: raise ValueError(f"Missing fields: {sorted(missing)}")
    if case["schema_version"] != 1: raise ValueError("Unsupported schema version")
    if case["kind"] not in KINDS: raise ValueError("Invalid kind")
    if case["expected"]["status"] not in STATES: raise ValueError("Invalid expected status")
    if case["expected"].get("trust") not in {"curated-reference", "upstream-unreviewed"}:
        raise ValueError("Missing or invalid reference trust level")
    if not isinstance(case["domains"], dict) or any(d not in {"real", "complex", "positive"} for d in case["domains"].values()):
        raise ValueError("Unsupported domain")
    if case["kind"] in {"definite", "principal-value", "numerical"} and "bounds" not in case:
        raise ValueError("Missing bounds")
    if case["kind"] == "contour" and "contour" not in case: raise ValueError("Missing contour")
    if "bounds" in case and (not isinstance(case["bounds"], list) or len(case["bounds"]) != 2):
        raise ValueError("Bounds must have two endpoints")
    if not isinstance(case["assumptions"], list): raise ValueError("Assumptions must be explicit")
    if case["family"] not in family_ids():
        raise ValueError(f"Unknown family: {case['family']}")
    return case


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def semantic_key(case):
    # Alpha-rename only the integration variable, not parameters or operators.
    # No algebraic simplifications that could change a branch or singularity.
    def rename(x):
        if isinstance(x, str): return "$variable" if x == case["variable"] else x
        if isinstance(x, list): return [rename(a) for a in x]
        if isinstance(x, dict):
            return {("$variable" if k == case["variable"] else k): rename(v) for k, v in x.items()}
        return x
    return digest({key: rename(case.get(key)) for key in
                   ("kind", "integrand", "bounds", "contour", "domains", "assumptions", "branches")})


def load_cases(path):
    # Do not retain a second corpus-sized string and split-lines list.
    with Path(path).open(encoding='utf-8') as stream:
        cases = [validate(json.loads(line)) for line in stream if line.strip()]
    ids = [c["id"] for c in cases]
    if len(set(ids)) != len(ids): raise ValueError("Duplicate case IDs")
    return cases


@dataclass(frozen=True)
class PreparedCorpus:
    """Internal read-only snapshot shared by paired runs, not a result cache.

    The case dictionaries are borrowed, never modified by runner/checkpoint code.
    Each source ID still receives an independent solve and verification attempt.
    """
    path: Path
    cases: list
    sha256: str

    @classmethod
    def load(cls, path):
        path = Path(path).resolve()
        cases = load_cases(path)
        return cls(path, cases, digest(cases))

    def for_path(self, path):
        if self.path != Path(path).resolve():
            raise ValueError('Prepared corpus path does not match requested corpus')
        return self.cases, self.sha256


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def infer_family(expr, kind="indefinite"):
    h = set(heads(expr))
    if h & {"Floor", "Ceiling", "FractionalPartFloor"}: return "piecewise-discrete"
    if h & {"Abs", "Sign", "Min", "Max"}: return "piecewise-absolute"
    if h & {"EllipticF", "EllipticE", "EllipticK", "EllipticPi"}: return "elliptic"
    if h & {"BesselJ", "BesselY", "BesselI", "BesselK"}: return "bessel"
    if h & {"Gamma", "Beta", "Zeta", "PolyGamma", "Digamma"}: return "gamma-beta-zeta"
    if h & {"Hypergeometric", "AppellF1", "PolyLog"}: return "hypergeometric-polylog"
    if h & {"Erf", "Erfc", "Erfi", "Ei", "Si", "Ci", "FresnelS", "FresnelC", "ExpIntegral", "LambertW"}: return "special-other"
    if h & {"Arcsin", "Arccos", "Arctan", "Arccot", "Arcsec", "Arccsc"}: return "inverse-trigonometric"
    if h & {"Arsinh", "Arcosh", "Artanh", "Arcoth", "Arsech", "Arcsch"}: return "inverse-hyperbolic"
    if h & {"Sinh", "Cosh", "Tanh", "Coth", "Sech", "Csch"}: return "hyperbolic"
    if h & {"Sin", "Cos", "Tan", "Cot", "Sec", "Csc"}: return "trigonometric"
    if "Exp" in h and "Log" in h: return "exponential-logarithmic"
    if "Exp" in h: return "exponential"
    if "Log" in h: return "logarithmic"
    if "Sqrt" in h or "RealRoot" in h: return "algebraic-radicals"
    # General powers include parameter exponents; do not mislabel them rational.
    if "Power" in h: return "algebraic-general"
    return "rational-polynomial"
