"""Two-phase, fresh-process protocol. A setup timeout is not a solver timeout."""

import json
import os
import queue
import subprocess
import threading
import time
from .model import ROOT


def invoke_phased(command, request, setup_timeout, solve_timeout, env=None):
    start = time.perf_counter()
    events = queue.Queue(maxsize=4)
    stderr = bytearray()
    process = None
    threads = []
    ready = None
    phase_start = start
    phase = 'setup'

    def read_lines(stream):
        try:
            # A bounded line prevents a broken adapter from exhausting parent memory.
            for _ in range(3):
                line = stream.readline(8 * 1024 * 1024 + 1)
                if not line:
                    break
                if len(line) > 8 * 1024 * 1024:
                    events.put({'event': 'invalid', 'reason': 'Adapter line exceeds 8 MiB'})
                    return
                try:
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError('Expected an object')
                    events.put(value)
                except (ValueError, UnicodeError):
                    events.put({'event': 'invalid', 'reason': 'Invalid adapter JSON'})
                    return
            events.put({'event': 'eof'})
        except OSError:
            events.put({'event': 'eof'})

    def drain_errors(stream):
        while chunk := stream.read(4096):
            stderr.extend(chunk)
            del stderr[:-4096]

    def send_request(stream):
        try:
            stream.write((json.dumps(request) + '\n').encode('utf-8'))
            stream.flush()
        except (BrokenPipeError, OSError):
            pass  # The reader reports a process/protocol failure.
        finally:
            stream.close()

    def receive(deadline):
        return events.get(timeout=max(0, deadline - time.perf_counter()))

    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, cwd=ROOT,
                                   env={**os.environ, **(env or {})}, shell=False)
        for target, stream in [(read_lines, process.stdout), (drain_errors, process.stderr),
                               (send_request, process.stdin)]:
            thread = threading.Thread(target=target, args=(stream,), daemon=True)
            thread.start()
            threads.append(thread)
        # The adapter loads its engine before reading this line. No expected answer is sent.
        event = receive(start + setup_timeout)
        if event.get('event') != 'ready':
            result = {'status': 'setup-error', 'phase': 'setup',
                      'reason': event.get('reason', 'Adapter exited before ready')}
        else:
            ready = event
            phase_start = time.perf_counter()
            phase = 'solve'
            event = receive(phase_start + solve_timeout)
            if event.get('event') != 'result' or not isinstance(event.get('result'), dict):
                result = {'status': 'protocol-error', 'phase': phase,
                          'reason': event.get('reason', 'Expected one result after ready')}
            else:
                result = event['result']
                # No extra output or leaked process is accepted after a result.
                tail = receive(phase_start + solve_timeout)
                if tail.get('event') != 'eof':
                    result = {'status': 'protocol-error', 'phase': phase, 'reason': 'Extra adapter output'}
                process.wait(timeout=max(.001, phase_start + solve_timeout - time.perf_counter()))
                if process.returncode:
                    result = {'status': 'process-error', 'phase': phase}
    except (queue.Empty, subprocess.TimeoutExpired):
        result = {'status': 'setup-timeout' if phase == 'setup' else 'timeout', 'phase': phase}
    except OSError as exc:
        result = {'status': 'launch-error' if process is None else 'process-error',
                  'phase': phase, 'reason': str(exc)}
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            for thread in threads:
                thread.join(timeout=2)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream and not stream.closed:
                    stream.close()
    end = time.perf_counter()
    result['wall_ms'] = (end - start) * 1000
    result['setup_wall_ms'] = ((phase_start if ready else end) - start) * 1000
    if ready:
        result['solve_wall_ms'] = (end - phase_start) * 1000
        result['setup'] = {k: v for k, v in ready.items() if k != 'event'}
    if stderr and result.get('status') not in {'answer', 'unevaluated'}:
        result['stderr_tail'] = stderr.decode('utf-8', errors='replace')
    return result
