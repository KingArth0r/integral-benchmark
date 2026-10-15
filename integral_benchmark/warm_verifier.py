"""Opt-in import reuse for verification, with hard timeout and process recycling.

Each runner thread owns its own single-worker spawn pool. No solver runs here.
Imports are reused; SymPy assumptions and registered symbolic caches are cleared
before and after each request. This is not fresh-process isolation: fresh mode
remains the reference. A timeout discards the entire pool before reuse.
"""

import math
import multiprocessing as mp
import time


def verify_request(request):
    import sympy as s
    from sympy.core.cache import clear_cache
    from .verifier import verify
    clear_cache()
    s.assumptions.global_assumptions.clear()
    try:
        return verify(request['case'], request['result'])
    except Exception as exc:
        return {'verdict': 'verifier-error', 'detail': f'{type(exc).__name__}: {exc}'}
    finally:
        s.assumptions.global_assumptions.clear()
        clear_cache()


class WarmVerifier:
    """Serial client. Pool queues correlate responses, including after a restart."""
    def __init__(self, max_cases=100, worker=verify_request):
        if type(max_cases) is not int or max_cases < 1:
            raise ValueError('Verifier recycle count must be a positive integer')
        self.max_cases = max_cases
        self.worker = worker
        self.pool = None

    def invoke(self, request, timeout):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Verification timeout must be positive and finite')
        start = time.perf_counter()
        try:
            if self.pool is None:
                self.pool = mp.get_context('spawn').Pool(1, maxtasksperchild=self.max_cases)
            remaining = timeout - (time.perf_counter() - start)
            if remaining <= 0:
                raise mp.TimeoutError
            response = self.pool.apply_async(self.worker, (request,)).get(timeout=remaining)
            if not isinstance(response, dict) or not isinstance(response.get('verdict'), str):
                self.close()
                response = {'verdict': 'verifier-error', 'detail': 'Invalid warm verifier response'}
        except mp.TimeoutError:
            self.close()
            response = {'status': 'timeout', 'verdict': 'verification-timeout'}
        except Exception as exc:
            self.close()
            response = {'verdict': 'verifier-error', 'detail': f'{type(exc).__name__}: {exc}'}
        return {**response, 'wall_ms': (time.perf_counter() - start) * 1000}

    def close(self):
        if self.pool is not None:
            pool, self.pool = self.pool, None
            pool.terminate()
            pool.join()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
