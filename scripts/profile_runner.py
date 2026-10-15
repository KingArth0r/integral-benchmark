"""Read ALL completed evidence and compare verifier startup on a synthetic fixture.

This is a harness microbenchmark, not a sampled integral-coverage evaluation.
Run with `python -m scripts.profile_runner --run ... --output ...`.
"""

import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
from integral_benchmark.model import write_json
from integral_benchmark.runner import invoke
from integral_benchmark.warm_verifier import WarmVerifier


def summarize(path):
    records = []
    # A live journal may end with a partly written line. Never consume that line.
    with (Path(path)/'results.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            if not line.endswith('\n'): break
            records.append(json.loads(line))
    result = {'completed_prefix_only': True, 'records': len(records), 'timings': {}}
    for key, field in [('setup', 'setup_wall_ms'), ('solve', 'solve_wall_ms'), ('integrate', 'solver_ms')]:
        values = [r['result'][field] for r in records if field in r['result']]
        result['timings'][key] = {'count': len(values), 'sum_ms': sum(values),
                                  'median_ms': statistics.median(values) if values else None}
    values = [r['verification']['wall_ms'] for r in records if r['verification'].get('wall_ms', 0) > 0]
    result['timings']['verification'] = {'count': len(values), 'sum_ms': sum(values),
                                        'median_ms': statistics.median(values) if values else None}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', default=[])
    parser.add_argument('--repeats', type=int, default=6)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.repeats < 2: parser.error('Use at least two repetitions')
    request = {'case': {'kind': 'indefinite', 'integrand': ['Multiply', 2, 'x'],
        'variable': 'x', 'domains': {'x': 'real'}, 'assumptions': [],
        'expected': {'status': 'finite', 'trust': 'curated-reference'}},
        'result': {'status': 'answer', 'answer': ['Power', 'x', 2]}}
    evidence = {'python': platform.python_version(),
                'scope': 'Synthetic derivative-check fixture; NOT corpus coverage or an end-to-end speed claim',
                'live_runs': {Path(p).name: summarize(p) for p in args.run}, 'samples': []}
    with WarmVerifier() as worker:
        for i in range(args.repeats):
            for mode in (('fresh', 'warm') if i % 2 == 0 else ('warm', 'fresh')):
                response = (invoke([sys.executable, '-m', 'integral_benchmark.verifier'], request, 20)
                            if mode == 'fresh' else worker.invoke(request, 20))
                if response.get('verdict') != 'identity-checked':
                    raise RuntimeError(f'Fixture failed: {response}')
                evidence['samples'].append({'mode': mode, 'iteration': i, 'wall_ms': response['wall_ms']})
    evidence['summary'] = {mode: {'median_ms': statistics.median(
        s['wall_ms'] for s in evidence['samples'] if s['mode'] == mode),
        'total_ms': sum(s['wall_ms'] for s in evidence['samples'] if s['mode'] == mode)} for mode in ('fresh', 'warm')}
    write_json(args.output, evidence)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__': main()
