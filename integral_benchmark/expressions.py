"""A small exact expression interchange language; never evaluate source text."""

import ast
import math
import re


FUNCTIONS = {
    "sin": "Sin", "cos": "Cos", "tan": "Tan", "cot": "Cot",
    "sec": "Sec", "csc": "Csc", "asin": "Arcsin", "acos": "Arccos",
    "atan": "Arctan", "acot": "Arccot", "asec": "Arcsec", "acsc": "Arccsc",
    "sinh": "Sinh", "cosh": "Cosh", "tanh": "Tanh", "coth": "Coth",
    "sech": "Sech", "csch": "Csch", "asinh": "Arsinh", "acosh": "Arcosh",
    "atanh": "Artanh", "acoth": "Arcoth", "asech": "Arsech", "acsch": "Arcsch",
    "log": "Log", "ln": "Log", "exp": "Exp", "sqrt": "Sqrt", "Abs": "Abs",
    "erf": "Erf", "erfc": "Erfc", "erfi": "Erfi", "Ei": "Ei",
    "Si": "Si", "Ci": "Ci", "gamma": "Gamma", "uppergamma": "UpperGamma",
    "lowergamma": "LowerGamma", "beta": "Beta", "zeta": "Zeta",
    "polylog": "PolyLog", "digamma": "Digamma", "polygamma": "PolyGamma",
    "LambertW": "LambertW", "besselj": "BesselJ", "bessely": "BesselY",
    "besseli": "BesselI", "besselk": "BesselK", "elliptic_f": "EllipticF",
    "elliptic_e": "EllipticE", "elliptic_k": "EllipticK", "elliptic_pi": "EllipticPi",
    "floor": "Floor", "ceiling": "Ceiling", "sign": "Sign", "frac": "FractionalPartFloor",
    "Min": "Min", "Max": "Max", "real_root": "RealRoot",
    "hyper": "Hypergeometric", "appellf1": "AppellF1",
    "expint": "ExpIntegral", "fresnels": "FresnelS", "fresnelc": "FresnelC",
    "re": "Real", "im": "Imaginary", "conjugate": "Conjugate", "loggamma": "LogGamma",
}
CONSTANTS = {"pi": "Pi", "E": "ExponentialE", "I": "ImaginaryUnit",
             "oo": "PositiveInfinity", "EulerGamma": "EulerGamma", "Catalan": "CatalanConstant"}
ARITIES = {"Subtract": (2, 2), "Divide": (2, 2), "Power": (2, 2), "Rational": (2, 2),
           "Negate": (1, 1), "Complex": (2, 2), "Add": (1, 10000), "Multiply": (1, 10000)}


class TranslationError(ValueError):
    pass


def parse(text):
    """Parse the supported Python/SymPy expression subset without eval/sympify."""
    if not isinstance(text, str) or len(text) > 1_000_000:
        raise TranslationError("Expression must be a bounded string")

    def visit(n):
        if isinstance(n, ast.Constant) and type(n.value) is int:
            return n.value
        if isinstance(n, ast.Constant) and type(n.value) is float and math.isfinite(n.value):
            # Decimal literals stay exact strings; never round via binary float in an adapter.
            return {"decimal": ast.get_source_segment(text, n)}
        if isinstance(n, ast.Name) and not n.id.startswith("_"):
            return CONSTANTS.get(n.id, n.id)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            value = visit(n.operand)
            return value if isinstance(n.op, ast.UAdd) else ["Negate", value]
        if isinstance(n, ast.BinOp):
            head = {ast.Add: "Add", ast.Sub: "Subtract", ast.Mult: "Multiply",
                    ast.Div: "Divide", ast.Pow: "Power"}.get(type(n.op))
            if head:
                return [head, visit(n.left), visit(n.right)]
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and not n.keywords:
            if n.func.id == "Rational" and len(n.args) == 2:
                return ["Rational", *(visit(a) for a in n.args)]
            if n.func.id in FUNCTIONS:
                return [FUNCTIONS[n.func.id], *(visit(a) for a in n.args)]
        if isinstance(n, (ast.Tuple, ast.List)):
            return ["Tuple", *(visit(a) for a in n.elts)]
        name = n.func.id if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) else None
        raise TranslationError(f"Unsupported syntax: {type(n).__name__}" + (f" ({name})" if name else ""))

    try:
        return visit(ast.parse(text, mode="eval").body)
    except (SyntaxError, RecursionError) as exc:
        raise TranslationError(str(exc)) from exc


def heads(expr):
    if isinstance(expr, list):
        yield expr[0]
        for child in expr[1:]:
            yield from heads(child)


def symbols(expr):
    if isinstance(expr, str) and expr not in set(CONSTANTS.values()) | {"NegativeInfinity"}:
        yield expr
    elif isinstance(expr, list):
        for child in expr[1:]:
            yield from symbols(child)


def to_sympy(expr, domains=None, branch_obligations=None):
    import sympy as s
    domains = domains or {}
    constants = {"Pi": s.pi, "ExponentialE": s.E, "ImaginaryUnit": s.I,
                 "PositiveInfinity": s.oo, "NegativeInfinity": -s.oo,
                 "EulerGamma": s.EulerGamma, "CatalanConstant": s.Catalan,
                 "True": s.true, "False": s.false}
    functions = {head: getattr(s, name) for name, head in FUNCTIONS.items()}
    if type(expr) is int:
        return s.Integer(expr)
    if isinstance(expr, str):
        if expr in constants:
            return constants[expr]
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", expr):
            raise TranslationError(f"Invalid symbol {expr!r}")
        domain = domains.get(expr, "complex")
        return s.Symbol(expr, **(domain if isinstance(domain, dict) else {"real": True} if domain == "real" else
                                {"positive": True} if domain == "positive" else {}))
    if isinstance(expr, dict) and set(expr) == {"decimal"}:
        return s.Rational(expr["decimal"])
    if not isinstance(expr, list) or not expr:
        raise TranslationError(f"Unsupported expression {str(expr)[:120]}")
    head, *raw = expr
    args = [to_sympy(x, domains, branch_obligations) for x in raw]
    if head in ARITIES and not ARITIES[head][0] <= len(args) <= ARITIES[head][1]:
        raise TranslationError(f"Invalid arity for {head}")
    if head == "Add": return s.Add(*args)
    if head == "Multiply": return s.Mul(*args)
    if head == "Subtract": return args[0] - args[1]
    if head in ("Divide", "Rational"): return args[0] / args[1]
    if head == "Power": return args[0] ** args[1]
    if head == "Negate": return -args[0]
    if head == "Complex": return args[0] + s.I * args[1]
    if head == "Tuple": return s.Tuple(*args)
    if head in {'CERoot', 'CEPower'}:
        if len(args) != 2: raise TranslationError(f'Invalid arity for {head}')
        base, exponent = args
        if head == 'CERoot':
            if not exponent.is_Integer or exponent == 0:
                raise TranslationError('CE root requires a nonzero integer degree for verification')
            exponent = 1 / exponent
        if exponent.is_Rational:
            if exponent.q % 2 == 0 or exponent.q == 1 or base.is_nonnegative:
                return base ** exponent
            if base.is_real:
                return s.real_root(base, exponent.q) ** exponent.p
            if base.is_real is False:
                return base ** exponent
        elif base.is_positive:
            return base ** exponent
        # Use the principal branch ONLY for a separately labelled local check.
        # This is not an export of CE's full branch-dependent value.
        if branch_obligations is None:
            raise TranslationError('CE root/power branch needs a domain restriction')
        branch_obligations.append({'expression': expr, 'restriction': 'base outside the negative real axis'})
        return base ** exponent
    predicates = {'Equal': s.Eq, 'NotEqual': s.Ne, 'Less': s.Lt, 'LessEqual': s.Le,
                  'Greater': s.Gt, 'GreaterEqual': s.Ge, 'And': s.And, 'Or': s.Or, 'Not': s.Not}
    if head in predicates: return predicates[head](*args)
    if head == 'Which':
        if len(args) % 2: raise TranslationError('Which needs condition/value pairs')
        return s.Piecewise(*[(args[i+1], args[i]) for i in range(0, len(args), 2)])
    if head in functions: return functions[head](*args)
    raise TranslationError(f"Unsupported operator {head}")


def from_sympy(expr):
    import sympy as s
    constants = {s.pi: "Pi", s.E: "ExponentialE", s.I: "ImaginaryUnit",
                 s.oo: "PositiveInfinity", -s.oo: "NegativeInfinity",
                 s.EulerGamma: "EulerGamma", s.Catalan: "CatalanConstant"}
    if expr == s.true: return 'True'
    if expr == s.false: return 'False'
    if expr in constants: return constants[expr]
    if isinstance(expr, s.Integer): return int(expr)
    if isinstance(expr, s.Rational): return ["Rational", int(expr.p), int(expr.q)]
    if isinstance(expr, s.Float): return {"decimal": str(expr)}
    if isinstance(expr, s.Symbol): return str(expr)
    if isinstance(expr, s.Tuple): return ["Tuple", *(from_sympy(a) for a in expr)]
    head = {s.Add: "Add", s.Mul: "Multiply", s.Pow: "Power"}.get(expr.func)
    if head is None:
        head = FUNCTIONS.get(expr.func.__name__)
    if head is None: raise TranslationError(f"Cannot export {expr.func}")
    return [head, *(from_sympy(a) for a in expr.args)]
