"""Original regression cases supplement, never replace, source-complete acquisition."""
import json
from pathlib import Path
from integral_benchmark.expressions import parse
from integral_benchmark.model import infer_family, validate


def build():
    rows = [
        ('floor', 'floor(x)', '0', '3', '3', 'Sum of cell areas 0+1+2.'),
        ('ceiling', 'ceiling(x)', '0', '3', '6', 'Sum of cell areas 1+2+3; endpoint values have measure zero.'),
        ('fractional', 'frac(x)', '0', '3', '3/2', 'Three periods, each with area 1/2.'),
        ('floor-negative', 'floor(x)', '-3/2', '3/2', '-3/2', 'Cell areas -1-1+0+1/2.'),
        ('ceiling-negative', 'ceiling(x)', '-3/2', '3/2', '3/2', 'Ceiling(x)=-Floor(-x); reflect the interval.'),
        ('fractional-negative', 'frac(x)', '-3/2', '3/2', '3/2', 'Three full unit periods of the floor-based fractional part.'),
        ('floor-affine', 'floor(2*x+1/2)', '0', '1', '1', 'Breakpoints at 1/4 and 3/4; cell areas 0+1/2+1/2.'),
        ('floor-negative-slope', 'floor(1-2*x)', '0', '1', '-1/2', 'Value 0 on (0,1/2), -1 on (1/2,1).'),
        ('floor-reversed', 'floor(x)', '3', '0', '-3', 'Reverse the bounds of the floor control case.'),
        ('minimum', 'Min(x,1-x)', '0', '1', '1/4', 'Two triangles meeting at x=1/2.'),
        ('maximum', 'Max(x,1-x)', '0', '1', '3/4', 'Min+Max=x+(1-x)=1; subtract 1/4 from 1.'),
        ('maximum-polynomial', 'Max(x,x**2)', '0', '2', '17/6', 'Integrate x on [0,1] and x^2 on [1,2].'),
        ('floor-polynomial', 'floor(x**2)', '0', '2', '5-sqrt(2)-sqrt(3)', 'Cuts at 1,sqrt(2),sqrt(3); areas (sqrt(2)-1)+2(sqrt(3)-sqrt(2))+3(2-sqrt(3)).'),
        ('weighted-floor', 'x*floor(x)', '0', '3', '13/2', 'Integrate x on [1,2] and 2x on [2,3].'),
        ('absolute-control', 'Abs(x)', '-1', '1', '1', 'Two triangles of area 1/2.'),
        ('absolute-periodic', 'Abs(sin(x))', '0', '2*pi', '4', 'Positive sine on [0,pi], negative sine on [pi,2pi].'),
        ('fractional-many-periods', 'frac(x)', '0', '1000000+1/2', '500000+1/8', 'One million complete periods plus integral of x on [0,1/2].'),
        ('fractional-reciprocal', 'frac(1/x)', '0', '1', '1-EulerGamma', 'Cell sums log((n+1)/n)-1/(n+1); partial sum log(N+1)-H_(N+1)+1 tends to 1-EulerGamma.'),
        ('floor-reciprocal-divergent', 'floor(1/x)', '0', '1', None, 'Cell integrals 1/(n+1) have divergent positive sum.'),
    ]
    result = []
    for identifier, f, a, b, answer, evidence in rows:
        expr = parse(f)
        result.append(validate({
            'schema_version': 1, 'id': 'discrete:' + identifier, 'kind': 'definite',
            'integrand': expr, 'variable': 'x', 'bounds': [parse(a), parse(b)],
            'domains': {'x': 'real'}, 'assumptions': [], 'assumptions_status': 'explicit',
            'branches': 'Real; fractional part means x-Floor(x); ordinary improper endpoints, not principal value.',
            'parameters': [], 'family': infer_family(expr), 'classification': 'curated',
            'source': {'suite': 'original-discrete-regressions', 'locator': identifier, 'redistribution': 'project-license'},
            'expected': {'status': 'finite' if answer else 'divergent',
                         'expression': parse(answer) if answer else None,
                         'trust': 'curated-reference', 'evidence': evidence},
        }))
    # Retain a known native CE failure even before adapters support Boolean branches.
    branch = json.loads(json.dumps(next(c for c in result if c['id']=='discrete:absolute-control')))
    branch.update(id='discrete:explicit-which', integrand=['Which',['Less','x',0],['Negate','x'],'True','x'])
    branch['source']['locator'] = 'explicit-which'
    branch['expected']['evidence'] = 'First-true selector equals Abs(x) everywhere; no missing default branch.'
    result.append(validate(branch))
    return result


if __name__ == '__main__':
    path = Path('corpus/discrete-regressions.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    cases = build()
    path.write_text(''.join(json.dumps(c, ensure_ascii=False)+'\n' for c in cases), encoding='utf-8')
    print(f'Wrote {len(cases)} original regression cases')
