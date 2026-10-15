"""Conservative shared-symbol context for explicit scalar parameter assumptions."""

import sympy as s
from .expressions import to_sympy, TranslationError


def context(case):
    domains = dict(case['domains'])
    predicates = []

    def collect(expr):
        if isinstance(expr, list) and expr and expr[0] == 'And':
            for child in expr[1:]: collect(child)
        else:
            predicates.append(expr)

    for expr in case['assumptions']: collect(expr)
    constraints = {}
    for expr in predicates:
        if not isinstance(expr, list) or len(expr) != 3:
            raise TranslationError('Verifier supports scalar symbol/constant assumptions only')
        head, name, bound = expr
        if head not in {'Greater', 'GreaterEqual', 'Less', 'LessEqual', 'NotEqual'} or not isinstance(name, str):
            raise TranslationError('Unsupported verifier assumption; no condition was discarded')
        value = to_sympy(bound)
        if not value.is_real or value.free_symbols or value.is_finite is not True:
            raise TranslationError('Assumption bound must be a finite real constant')
        previous = domains.get(name, 'complex')
        facts = dict(previous) if isinstance(previous, dict) else (
            {'positive': True} if previous == 'positive' else {'real': True} if previous == 'real' else {})
        if head != 'NotEqual': facts['real'] = True
        if head == 'Greater' and value.is_nonnegative: facts['positive'] = True
        if head == 'GreaterEqual' and value.is_positive: facts['positive'] = True
        if head == 'GreaterEqual' and value == 0: facts['nonnegative'] = True
        if head == 'Less' and value.is_nonpositive: facts['negative'] = True
        if head == 'LessEqual' and value.is_negative: facts['negative'] = True
        if head == 'LessEqual' and value == 0: facts['nonpositive'] = True
        if head == 'NotEqual' and value == 0: facts['zero'] = False
        domains[name] = facts
        constraints.setdefault(name, []).append(expr)
    # Recreate all symbols with the final facts before building any expression.
    for name, exprs in constraints.items():
        symbol = to_sympy(name, domains)
        relations = [to_sympy(expr, domains) for expr in exprs]
        if any(r is s.false for r in relations):
            raise TranslationError('Contradictory assumptions')
        if symbol.is_real and s.reduce_inequalities(relations, symbol) is s.false:
            raise TranslationError('Contradictory assumptions')
    condition = s.And(*(to_sympy(expr, domains) for expr in predicates))
    return domains, condition
