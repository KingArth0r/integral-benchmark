"""Append-only run evidence, exclusive writers, and bounded resumable batches."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from .model import digest


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


@contextmanager
def writer_lock(output):
    """OS lock is released even if the process is killed; file is not a PID claim."""
    with (Path(output) / '.run.lock').open('a+b') as stream:
        stream.seek(0, 2)
        if not stream.tell():
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('Another process is writing this run') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def execute(output, metadata, cases, one, jobs=1, resume=False, batch_size=None):
    if jobs < 1 or (batch_size is not None and batch_size < 1):
        raise ValueError('Jobs and batch size must be positive')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with writer_lock(output):
        try:
            return _execute(output, metadata, cases, one, jobs, resume, batch_size)
        except (RuntimeError, OSError, KeyboardInterrupt) as exc:
            # Completed evidence is immutable. Mark interrupted runs, not false
            # completion, when a worker or disk fails; resume revalidates it all.
            for name in ('progress.json', 'run.json'):
                path = output / name
                if path.exists():
                    state = json.loads(path.read_text(encoding='utf-8'))
                    state.update(status='interrupted', interruption=type(exc).__name__)
                    atomic_json(path, state)
            raise


def _execute(output, metadata, cases, one, jobs, resume, batch_size):
    manifest, journal = output / 'run.json', output / 'results.jsonl'
    records = []
    by_id = {case['id']: case for case in cases}
    if len(by_id) != len(cases):
        raise ValueError('Duplicate case IDs')
    fingerprint = digest({k: v for k, v in metadata.items() if k != 'started_utc'})
    if resume:
        if not manifest.is_file():
            raise ValueError('Cannot resume without run.json')
        old = json.loads(manifest.read_text(encoding='utf-8'))
        if old.get('configuration_sha256') != fingerprint:
            raise ValueError('Resume configuration changed: use a new output directory')
        seen = set()
        if not journal.exists() and old.get('completed', 0):
            raise ValueError('Saved results are missing; do not silently restart this run')
        if journal.exists():
            with journal.open(encoding='utf-8') as stream:
                for line in stream:
                    try:
                        record = json.loads(line)
                    except ValueError as exc:
                        raise ValueError('Damaged journal; preserve and repair it before resuming') from exc
                    identifier = record.get('id')
                    if identifier in seen or identifier not in by_id:
                        raise ValueError('Duplicate or unexpected result ID')
                    if record.get('case_sha256') != digest(by_id[identifier]):
                        raise ValueError('Result case hash does not match corpus')
                    if not isinstance(record.get('result'), dict) or not isinstance(record.get('verification'), dict):
                        raise ValueError('Invalid saved result')
                    seen.add(identifier)
                    records.append(record)
        metadata = old
        metadata['resume_count'] = metadata.get('resume_count', 0) + 1
    elif manifest.exists() or journal.exists():
        raise ValueError('Output already contains evidence; use --resume or a new directory')
    else:
        metadata = {**metadata, 'configuration_sha256': fingerprint, 'resume_count': 0}
    done = {r['id'] for r in records}
    pending = [case for case in cases if case['id'] not in done]
    batch = pending if batch_size is None else pending[:batch_size]
    metadata.pop('finished_utc', None)
    metadata.update(status='running', completed=len(records))
    atomic_json(manifest, metadata)
    outcomes = Counter(r['result']['status'] for r in records)
    verdicts = Counter(r['verification']['verdict'] for r in records)

    def checkpoint(status):
        atomic_json(output / 'progress.json', {
            'updated_utc': datetime.now(timezone.utc).isoformat(), 'status': status,
            'completed': len(records), 'case_count': len(cases),
            'remaining': len(cases) - len(records),
            'solver_outcomes': dict(outcomes), 'verification': dict(verdicts),
        })

    checkpoint('running')
    infrastructure_streak = 0
    # Never enqueue the entire corpus: at most jobs tasks are in flight.
    with journal.open('ab') as log:
        if log.tell():
            with journal.open('rb') as previous:
                previous.seek(-1, os.SEEK_END)
                if previous.read(1) != b'\n':
                    log.write(b'\n')  # A complete last JSON record without newline is valid.
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            iterator = iter(batch)
            futures = {}

            def submit():
                case = next(iterator, None)
                if case is not None:
                    futures[pool.submit(one, case)] = case['id']

            for _ in range(jobs): submit()
            while futures:
                completed, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in completed:
                    expected_id = futures.pop(future)
                    record = future.result()
                    if record['id'] != expected_id or record['case_sha256'] != digest(by_id[expected_id]):
                        raise ValueError('Worker returned evidence for a different case')
                    log.write((json.dumps(record, ensure_ascii=False) + '\n').encode('utf-8'))
                    log.flush()
                    os.fsync(log.fileno())
                    records.append(record)
                    outcomes[record['result']['status']] += 1
                    verdicts[record['verification']['verdict']] += 1
                    checkpoint('running')
                    print(f"{len(records)}/{len(cases)} {record['id']} {record['result']['status']} {record['verification']['verdict']}", flush=True)
                    infrastructure_streak = infrastructure_streak + 1 if record['verification']['verdict'] == 'infrastructure-error' else 0
                    if infrastructure_streak >= 3:
                        raise RuntimeError('Three consecutive infrastructure failures; evidence saved, repair before resuming')
                    submit()
    status = 'complete' if len(records) == len(cases) else 'partial'
    metadata.update(status=status, completed=len(records), last_batch_completed=len(batch))
    if status == 'complete': metadata['finished_utc'] = datetime.now(timezone.utc).isoformat()
    atomic_json(manifest, metadata)
    checkpoint(status)
    return records
