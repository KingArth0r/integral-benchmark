"""Run every imported Rubi case in both CE configurations. No sampling options."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import threading
from .checkpoint import atomic_json, writer_lock
from .model import load_cases, digest
from .runner import run, harness_digest


def audit(corpus, inventory, expected_count):
    cases = load_cases(corpus)
    source = json.loads(Path(inventory).read_text(encoding='utf-8'))
    rubi = source['suites']['rubi']
    if len(cases) != expected_count:
        raise ValueError(f'Full corpus count mismatch: {len(cases)} != {expected_count}')
    if rubi['records'] != len(cases) + rubi['translation_failed']:
        raise ValueError('Imported cases plus translation failures do not account for every source record')
    if any(c['source']['suite'] != 'rubi' or c['source']['revision'] != source['revision'] for c in cases):
        raise ValueError('Corpus source/revision mismatch')
    return {'runnable_cases_per_configuration': len(cases),
            'source_records': rubi['records'], 'translation_failures': rubi['translation_failed'],
            'source_revision': source['revision'], 'corpus_sha256': digest(cases),
            'inventory_sha256': hashlib.sha256(Path(inventory).read_bytes()).hexdigest(),
            'assumptions_review_required': sum(c.get('assumptions_status') == 'not-specified-upstream' for c in cases),
            'parameter_cases': sum(bool(c.get('parameters')) for c in cases)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('corpus', 'inventory', 'ce-root', 'ce-module', 'ce-rules-module', 'output'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--expected-count', type=int, required=True)
    parser.add_argument('--jobs', type=int, default=2, help='Jobs per configuration (twice this many total)')
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--setup-timeout', type=float, default=120)
    parser.add_argument('--verify-timeout', type=float, default=20)
    parser.add_argument('--rule-step-budget', type=int, default=300000)
    parser.add_argument('--node', default='node')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.jobs < 1 or args.expected_count < 1:
        parser.error('Jobs and expected count must be positive')
    for key in ('corpus', 'inventory', 'ce_root', 'ce_module', 'ce_rules_module', 'output'):
        setattr(args, key, str(Path(getattr(args, key)).resolve()))
    if subprocess.check_output(['git', '-C', args.ce_root, 'status', '--porcelain'], text=True).strip():
        raise ValueError('Full baselines require a clean, pinned CE checkout')
    accounting = audit(args.corpus, args.inventory, args.expected_count)
    config = {k: v for k, v in vars(args).items() if k != 'resume'}
    config['accounting'] = accounting
    config['harness_sha256'] = harness_digest()
    config['ce_revision'] = subprocess.check_output(['git', '-C', args.ce_root, 'rev-parse', 'HEAD'], text=True).strip()
    for key in ('ce_module', 'ce_rules_module'):
        config[key + '_sha256'] = hashlib.sha256(Path(config[key]).read_bytes()).hexdigest()
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    with writer_lock(root):
        manifest = root / 'baseline.json'
        fingerprint = digest(config)
        if manifest.exists():
            if not args.resume:
                raise ValueError('Baseline exists; explicit --resume is required')
            state = json.loads(manifest.read_text(encoding='utf-8'))
            if state['configuration_sha256'] != fingerprint:
                raise ValueError('Baseline configuration changed; use a new directory')
        else:
            if args.resume: raise ValueError('Cannot resume a missing baseline')
            state = {'configuration': config, 'configuration_sha256': fingerprint,
                     'started_utc': datetime.now(timezone.utc).isoformat()}
        state['status'] = 'running'
        atomic_json(manifest, state)
        stop_event = threading.Event()

        def execute(rules):
            output = root / ('ce-rubi' if rules else 'ce')
            try:
                run(args.corpus, output, 'ce', timeout=args.timeout, verify_timeout=args.verify_timeout,
                    jobs=args.jobs, ce_root=args.ce_root, node=args.node, rules=rules,
                    ce_module=args.ce_module, ce_rules_module=args.ce_rules_module if rules else None,
                    resume=args.resume and (output/'run.json').exists(), setup_timeout=args.setup_timeout,
                    rule_step_budget=args.rule_step_budget, stop_event=stop_event)
            except BaseException:
                stop_event.set()
                raise
            progress = json.loads((output/'progress.json').read_text(encoding='utf-8'))
            if progress['completed'] != args.expected_count or progress['status'] != 'complete':
                raise RuntimeError('A configuration did not complete the entire corpus')
            return progress

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = {name: pool.submit(execute, rules) for name, rules in [('ce', False), ('ce-rubi', True)]}
                state['results'] = {name: future.result() for name, future in futures.items()}
            from .report import generate
            generate(args.corpus, args.inventory, [root/'ce', root/'ce-rubi'], root/'coverage')
            state['status'] = 'complete'
            state['finished_utc'] = datetime.now(timezone.utc).isoformat()
        except BaseException as exc:
            state.update(status='interrupted', interruption=type(exc).__name__)
            raise
        finally:
            atomic_json(manifest, state)


if __name__ == '__main__': main()
