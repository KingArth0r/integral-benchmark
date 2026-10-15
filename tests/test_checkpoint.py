import json
from pathlib import Path
import tempfile
import unittest
from integral_benchmark.checkpoint import execute, writer_lock
from integral_benchmark.model import digest


class Checkpoints(unittest.TestCase):
    def setUp(self):
        self.cases = [{'id': str(i), 'integrand': i} for i in range(5)]
        self.metadata = {'engine': 'fake', 'timeout': 10, 'started_utc': 'first'}
        self.called = []

    def solve(self, case):
        self.called.append(case['id'])
        return {'id': case['id'], 'case_sha256': digest(case),
                'result': {'status': 'unevaluated'}, 'verification': {'verdict': 'not-solved'}}

    def test_batches_resume_without_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            execute(d, self.metadata, self.cases, self.solve, jobs=2, batch_size=2)
            first = (Path(d) / 'results.jsonl').read_bytes()
            self.assertEqual(json.loads((Path(d) / 'run.json').read_text())['status'], 'partial')
            execute(d, {**self.metadata, 'started_utc': 'second'}, self.cases, self.solve, jobs=2, resume=True)
            self.assertTrue((Path(d) / 'results.jsonl').read_bytes().startswith(first))
            self.assertCountEqual(self.called, ['0', '1', '2', '3', '4'])
            execute(d, self.metadata, self.cases, self.solve, jobs=2, resume=True)
            self.assertEqual(len(self.called), 5)
            progress = json.loads((Path(d) / 'progress.json').read_text())
            self.assertEqual(progress['status'], 'complete')
            self.assertEqual(progress['remaining'], 0)

    def test_refuses_overwrite_and_changed_settings(self):
        with tempfile.TemporaryDirectory() as d:
            execute(d, self.metadata, self.cases, self.solve, batch_size=1)
            before = (Path(d) / 'results.jsonl').read_bytes()
            with self.assertRaises(ValueError): execute(d, self.metadata, self.cases, self.solve)
            with self.assertRaises(ValueError):
                execute(d, {**self.metadata, 'timeout': 11}, self.cases, self.solve, resume=True)
            self.assertEqual((Path(d) / 'results.jsonl').read_bytes(), before)

    def test_rejects_corrupt_duplicate_unknown_or_changed_case(self):
        for mode in ['corrupt', 'duplicate', 'unknown', 'hash']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as d:
                execute(d, self.metadata, self.cases, self.solve, batch_size=1)
                p = Path(d) / 'results.jsonl'
                r = json.loads(p.read_text())
                if mode == 'corrupt': content = p.read_text() + '{'
                elif mode == 'duplicate': content = p.read_text() * 2
                else:
                    r['id' if mode == 'unknown' else 'case_sha256'] = 'invalid'
                    content = json.dumps(r)
                p.write_text(content)
                with self.assertRaises(ValueError):
                    execute(d, self.metadata, self.cases, self.solve, resume=True)
                self.assertEqual(p.read_text(), content)

    def test_valid_last_record_without_newline(self):
        with tempfile.TemporaryDirectory() as d:
            execute(d, self.metadata, self.cases, self.solve, batch_size=1)
            p = Path(d) / 'results.jsonl'
            p.write_text(p.read_text().rstrip())
            execute(d, self.metadata, self.cases, self.solve, resume=True)
            self.assertEqual(len([json.loads(line) for line in p.read_text().splitlines()]), 5)

    def test_lock_released_after_exception(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                with writer_lock(d):
                    with self.assertRaises(ValueError):
                        with writer_lock(d): pass
                    raise RuntimeError('interrupted')
            with writer_lock(d): pass

    def test_resume_requires_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                execute(d, self.metadata, self.cases, self.solve, resume=True)

    def test_missing_recorded_journal_is_not_silently_recreated(self):
        with tempfile.TemporaryDirectory() as d:
            execute(d, self.metadata, self.cases, self.solve, batch_size=1)
            journal = Path(d) / 'results.jsonl'
            journal.unlink()
            with self.assertRaises(ValueError):
                execute(d, self.metadata, self.cases, self.solve, resume=True)
            self.assertFalse(journal.exists())


if __name__ == '__main__': unittest.main()
