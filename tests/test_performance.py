import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from integral_benchmark.model import PreparedCorpus, digest, load_cases
from integral_benchmark.runner import invoke, run
from integral_benchmark.seed import build
from integral_benchmark.warm_verifier import WarmVerifier, verify_request


def fault_worker(request):
    if request.get('action') == 'hang': time.sleep(20)
    if request.get('action') == 'crash': os._exit(7)
    if request.get('action') == 'bad': return ['not a response']
    return {'verdict': 'fixture', 'pid': os.getpid(), 'id': request.get('id')}


def contaminated_worker(request):
    import sympy as s
    s.assumptions.global_assumptions.add(s.Q.positive(s.Symbol('x')))
    result = verify_request(request)
    return {**result, 'global_assumptions_remaining': len(s.assumptions.global_assumptions)}


def fixture(integrand, answer, **overrides):
    case = {**build()[0], 'integrand': integrand, 'domains': {}, 'assumptions': [], **overrides}
    return {'case': case, 'result': {'status': 'answer', 'answer': answer}}


class WarmVerification(unittest.TestCase):
    def test_fresh_and_warm_verdicts_match_including_reordered_domains(self):
        requests = [
            fixture(1, 'x'),
            fixture(1, ['Abs', 'x'], domains={'x': 'positive'}),
            fixture(1, ['Abs', 'x']),
            fixture(['Digamma', 'x'], ['LogGamma', 'x']),
            fixture(['Power', 'x', ['Rational', -2, 3]], ['Multiply', 3, ['CERoot', 'x', 3]]),
            fixture(1, 'x', assumptions=[['Greater', 'x', 0], ['Less', 'x', 0]]),
            fixture(['Power', 'x', 2], 'x'),
        ]
        # A-B-A includes an identical symbol name with incompatible domains.
        requests.append(requests[1])
        with WarmVerifier(max_cases=3) as worker:
            for request in requests:
                cold = invoke([sys.executable, '-m', 'integral_benchmark.verifier'], request, 20)
                warm = worker.invoke(request, 20)
                cold.pop('wall_ms')
                warm.pop('wall_ms')
                self.assertEqual(warm, cold)

    def test_timeout_and_crash_discard_worker_and_never_deliver_stale_results(self):
        with WarmVerifier(worker=fault_worker) as worker:
            first = worker.invoke({'id': 'first'}, 10)
            for action in ('hang', 'crash'):
                failure = worker.invoke({'action': action, 'id': 'stale'}, .4)
                self.assertEqual(failure['verdict'], 'verification-timeout')
                self.assertLess(failure['wall_ms'], 5000)
                self.assertIsNone(worker.pool)
                recovered = worker.invoke({'id': 'fresh'}, 10)
                self.assertEqual(recovered['id'], 'fresh')
                self.assertNotEqual(first['pid'], recovered['pid'])

    def test_recycling_and_cleanup(self):
        before = {p.pid for p in mp.active_children()}
        with WarmVerifier(max_cases=2, worker=fault_worker) as worker:
            pids = [worker.invoke({}, 10)['pid'] for _ in range(3)]
            self.assertEqual(pids[0], pids[1])
            self.assertNotEqual(pids[1], pids[2])
        self.assertEqual({p.pid for p in mp.active_children()}, before)

    def test_bad_response_discards_worker(self):
        with WarmVerifier(worker=fault_worker) as worker:
            result = worker.invoke({'action': 'bad'}, 10)
            self.assertEqual(result['verdict'], 'verifier-error')
            self.assertIsNone(worker.pool)

    def test_sympy_global_assumptions_are_cleared(self):
        with WarmVerifier(worker=contaminated_worker) as worker:
            result = worker.invoke(fixture(1, 'x'), 20)
            self.assertEqual(result['verdict'], 'identity-checked')
            self.assertEqual(result['global_assumptions_remaining'], 0)

    def test_invalid_settings(self):
        for count in (0, -1, 1.5):
            with self.assertRaises(ValueError): WarmVerifier(count)
        with WarmVerifier() as worker:
            for budget in (0, float('nan'), float('inf')):
                with self.assertRaises(ValueError): worker.invoke({}, budget)
            self.assertIsNone(worker.pool)


class CorpusReuse(unittest.TestCase):
    def test_parallel_runner_uses_warm_workers_and_closes_them(self):
        before = {p.pid for p in mp.active_children()}
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            corpus = root/'cases.jsonl'
            cases = [{**build()[0], 'id': str(i), 'integrand': 1} for i in range(4)]
            corpus.write_text('\n'.join(json.dumps(c) for c in cases), encoding='utf-8')
            command = json.dumps([sys.executable, '-c',
                'import json,sys; r=json.load(sys.stdin); print(json.dumps({"status":"answer","answer":r["case"]["variable"]}))'])
            records = run(corpus, root/'run', 'fixture', external=command, jobs=2,
                          verifier_mode='warm', verify_timeout=20, verifier_recycle=2)
            self.assertEqual(len(records), 4)
            self.assertTrue(all(r['verification']['verdict'] == 'identity-checked' for r in records))
        self.assertEqual({p.pid for p in mp.active_children()}, before)

    def test_snapshot_preserves_hash_and_all_ids_without_reloading(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            corpus = root/'cases.jsonl'
            cases = [{**build()[0], 'id': str(i)} for i in range(4)]
            corpus.write_text('\n'.join(json.dumps(c) for c in cases), encoding='utf-8')
            snapshot = PreparedCorpus.load(corpus)
            self.assertEqual(snapshot.sha256, digest(cases))
            self.assertEqual(snapshot.cases, load_cases(corpus))
            with self.assertRaises(ValueError): snapshot.for_path(root/'other.jsonl')
            command = json.dumps([sys.executable, '-c', 'print(\'{"status":"unevaluated"}\')'])
            with patch('integral_benchmark.runner.load_cases', side_effect=AssertionError('Unexpected reload')):
                for name in ('a', 'b'):
                    records = run(corpus, root/name, 'fixture', external=command, jobs=2, prepared_corpus=snapshot)
                    self.assertCountEqual([r['id'] for r in records], ['0', '1', '2', '3'])
            self.assertEqual(snapshot.sha256, digest(snapshot.cases))

    def test_verifier_mode_is_in_resume_identity(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            corpus = root/'cases.jsonl'
            corpus.write_text(json.dumps(build()[0]), encoding='utf-8')
            command = json.dumps([sys.executable, '-c', 'print(\'{"status":"unevaluated"}\')'])
            run(corpus, root/'run', 'fixture', external=command)
            with self.assertRaisesRegex(ValueError, 'configuration changed'):
                run(corpus, root/'run', 'fixture', external=command, verifier_mode='warm', resume=True)


if __name__ == '__main__': unittest.main()
