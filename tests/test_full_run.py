import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from integral_benchmark.expressions import parse, to_sympy, TranslationError
from integral_benchmark.model import ROOT, digest
from integral_benchmark.phased import invoke_phased
from integral_benchmark.seed import build
from integral_benchmark.verifier import verify


class Phases(unittest.TestCase):
    def invoke(self, source, setup=3, solve=3):
        return invoke_phased([sys.executable, '-u', '-c', source], {}, setup, solve)

    def test_setup_not_charged_to_solver(self):
        result = self.invoke("import time; time.sleep(.4); print('{\"event\":\"ready\"}'); "
                             "print('{\"event\":\"result\",\"result\":{\"status\":\"unevaluated\"}}')", solve=.3)
        self.assertEqual(result['status'], 'unevaluated')
        self.assertGreater(result['setup_wall_ms'], 350)
        self.assertLess(result['solve_wall_ms'], 300)

    def test_setup_and_solver_timeouts_are_distinct(self):
        setup = self.invoke('import time; time.sleep(10)', setup=.2)
        solve = self.invoke("import time; print('{\"event\":\"ready\"}'); time.sleep(10)", solve=.2)
        self.assertEqual(setup['status'], 'setup-timeout')
        self.assertEqual(solve['status'], 'timeout')
        self.assertEqual(solve['phase'], 'solve')
        self.assertLess(solve['wall_ms'], 3000)

    def test_broken_protocols_and_exit(self):
        for source, status in [
            ("print('bad')", 'setup-error'),
            ("print('{\"event\":\"ready\"}'); print('bad')", 'protocol-error'),
            ("print('{\"event\":\"ready\"}')", 'protocol-error'),
            ("print('{\"event\":\"ready\"}'); print('{\"event\":\"ready\"}')", 'protocol-error'),
            ("print('{\"event\":\"ready\"}'); print('{\"event\":\"result\",\"result\":{\"status\":\"answer\"}}'); print('{}')", 'protocol-error'),
            ("print('{\"event\":\"ready\"}'); print('{\"event\":\"result\",\"result\":{\"status\":\"answer\"}}'); raise RuntimeError('boom')", 'process-error'),
        ]:
            with self.subTest(source=source): self.assertEqual(self.invoke(source)['status'], status)

    def test_stderr_is_drained_and_bounded(self):
        result = self.invoke("import sys; sys.stderr.write('x'*100000); print('{\"event\":\"setup-error\",\"reason\":\"bad load\"}')")
        self.assertEqual(result['status'], 'setup-error')
        self.assertLessEqual(len(result['stderr_tail']), 4096)

    def test_launch_error(self):
        result = invoke_phased(['__no_such_benchmark_engine__'], {}, 1, 1)
        self.assertEqual(result['status'], 'launch-error')

    def test_blocked_stdin_does_not_disable_deadline(self):
        result = invoke_phased([sys.executable, '-c', 'import time; time.sleep(10)'],
                               {'payload': 'x' * 1000000}, .2, .2)
        self.assertEqual(result['status'], 'setup-timeout')
        self.assertLess(result['wall_ms'], 3000)


class FullManifest(unittest.TestCase):
    def test_all_records_accounted_for_and_no_sampling_flag(self):
        from integral_benchmark.full_baseline import audit
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cases = [{**build()[0], 'id': str(i), 'source': {'suite': 'rubi', 'revision': 'pinned'}} for i in range(3)]
            corpus, inventory = root/'cases.jsonl', root/'inventory.json'
            corpus.write_text('\n'.join(json.dumps(c) for c in cases), encoding='utf-8')
            inventory.write_text(json.dumps({'revision': 'pinned', 'suites': {'rubi': {'records': 4, 'translation_failed': 1}}}), encoding='utf-8')
            self.assertEqual(audit(corpus, inventory, 3)['source_records'], 4)
            with self.assertRaises(ValueError): audit(corpus, inventory, 2)
            inventory.write_text(json.dumps({'revision': 'pinned', 'suites': {'rubi': {'records': 5, 'translation_failed': 1}}}), encoding='utf-8')
            with self.assertRaises(ValueError): audit(corpus, inventory, 3)
        help_text = subprocess.check_output([sys.executable, '-m', 'integral_benchmark.full_baseline', '--help'], text=True)
        self.assertNotIn('--limit', help_text)
        self.assertNotIn('--batch-size', help_text)

    def test_infrastructure_failure_is_preserved_and_stops_run(self):
        from integral_benchmark.checkpoint import execute
        cases = [{'id': str(i)} for i in range(5)]
        def fail(case):
            return {'id': case['id'], 'case_sha256': digest(case),
                    'result': {'status': 'setup-error'}, 'verification': {'verdict': 'infrastructure-error'}}
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError): execute(d, {'started_utc': 'now'}, cases, fail)
            records = (Path(d)/'results.jsonl').read_text().splitlines()
            self.assertEqual(len(records), 3)
            self.assertEqual(json.loads((Path(d)/'progress.json').read_text())['status'], 'interrupted')


class Semantics(unittest.TestCase):
    def case(self, integrand, **kwargs):
        return {**build()[0], 'integrand': parse(integrand), 'domains': {},
                'assumptions': [], 'parameters': [], **kwargs}

    def test_analytic_loggamma(self):
        result = verify(self.case('digamma(x)'), {'status': 'answer', 'answer': ['LogGamma', 'x']})
        self.assertEqual(result['verdict'], 'identity-checked')
        import sympy as s
        self.assertEqual(to_sympy(['LogGamma', 'x']), s.loggamma(s.Symbol('x')))
        with self.assertRaises(TranslationError): to_sympy(['GammaLn', 'x'])

    def test_root_distinguishes_real_and_principal(self):
        import sympy as s
        self.assertEqual(to_sympy(['CERoot', -8, 3]), -2)
        self.assertNotEqual(to_sympy(['Power', -8, ['Rational', 1, 3]]), -2)
        self.assertEqual(to_sympy(['CEPower', -8, ['Rational', 2, 3]]), 4)
        self.assertEqual(to_sympy(['CERoot', -4, 2]), 2*s.I)
        self.assertEqual(to_sympy(['CERoot', 8, -3]), s.Rational(1, 2))
        with self.assertRaises(TranslationError): to_sympy(['CERoot', 'x', 3])
        with self.assertRaises(TranslationError): to_sympy(['CERoot', 'x', 0])

    def test_unknown_root_domain_gets_restricted_not_global_identity(self):
        case = self.case('x**(-2/3)')
        answer = {'status': 'answer', 'answer': ['Multiply', 3, ['CERoot', 'x', 3]]}
        result = verify(case, answer)
        self.assertEqual(result['verdict'], 'identity-checked-restricted')
        self.assertTrue(result['branch_obligations'])
        case['domains'] = {'x': 'positive'}
        self.assertEqual(verify(case, answer)['verdict'], 'identity-checked')

    def test_assumptions_applied_and_contradictions_not_vacuously_verified(self):
        case = self.case('1', assumptions=[['Greater', 'x', 0]])
        result = {'status': 'answer', 'answer': ['Abs', 'x']}
        self.assertEqual(verify(case, result)['verdict'], 'identity-checked')
        case['assumptions'].append(['Less', 'x', 0])
        self.assertEqual(verify(case, result)['verdict'], 'unverified')
        case['assumptions'] = [['UnimplementedPredicate', 'x']]
        self.assertEqual(verify(case, result)['verdict'], 'unverified')

    def test_general_parameter_identity_does_not_certify_exceptions(self):
        case = self.case('x**a', parameters=['a'], assumptions_status='not-specified-upstream')
        result = verify(case, {'status': 'answer', 'answer': parse('x**(a+1)/(a+1)')})
        self.assertEqual(result['verdict'], 'identity-checked')
        self.assertEqual(result['parameter_completeness'], 'not-certified')

    def test_conditions_retained_not_promoted_to_answers(self):
        result = verify(self.case('x'), {'status': 'conditional',
            'answer': ['ConditionalExpression', ['Divide', ['Power', 'x', 2], 2], ['Greater', 'a', 0]]})
        self.assertEqual(result['verdict'], 'conditional-unverified')

    def test_which_and_boolean_translation(self):
        import sympy as s
        expr = ['Which', ['Less', 'x', 0], ['Negate', 'x'], 'True', 'x']
        x = s.Symbol('x', real=True)
        value = to_sympy(expr, {'x': 'real'})
        self.assertEqual(value.subs(x, -2), 2)
        self.assertEqual(value.subs(x, 3), 3)

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_ce_translation_decimal_roots_and_conditions(self):
        module = (ROOT/'integral_benchmark/adapters/ce-expressions.mjs').as_uri()
        source = f'''import {{input, output, inputBranchWarnings}} from {json.dumps(module)};
          import assert from 'node:assert/strict';
          assert.deepEqual(input({{decimal:'1.25e-2'}}), ['Rational', {{num:'125'}}, {{num:'10000'}}]);
          assert.throws(() => input({{decimal:'NaN'}}));
          assert.throws(() => input({{decimal:'1e999999'}}));
          assert.deepEqual(output(['Root','x',3]), ['CERoot','x',3]);
          assert.deepEqual(output(['Power',-8,['Rational',2,3]]), ['CEPower',-8,['Rational',2,3]]);
          assert.deepEqual(input(['Greater','a',0]), ['Greater','a',0]);
          assert.deepEqual(input(['Which',['Less','x',0],-1,'True',1]), ['Which',['Less','x',0],-1,'True',1]);
          assert.equal(inputBranchWarnings(['Power','x',['Rational',1,3]]).length,1);
          assert.equal(inputBranchWarnings(['Power','x',['Divide',1,2]]).length,0);
          assert.equal(inputBranchWarnings(['Power','x',['Rational',2,6]]).length,1);
          assert.equal(inputBranchWarnings(['Power','x',['Rational',1,3]],{{x:'positive'}}).length,0);
        '''
        subprocess.run(['node', '--input-type=module', '-e', source], check=True, capture_output=True, timeout=10)


@unittest.skipUnless(os.environ.get('BENCH_TEST_CE_MODULE'), 'Optional pinned CE integration fixtures')
class LiveCE(unittest.TestCase):
    def solve(self, f, assumptions=None):
        case = {**build()[0], 'integrand': f, 'assumptions': assumptions or [], 'domains': {}}
        return invoke_phased(['node', str(ROOT/'integral_benchmark/adapters/ce.mjs')],
            {'protocol_version': 2, 'case': case}, 90, 30,
            {'CE_MODULE': os.environ['BENCH_TEST_CE_MODULE'], 'CE_RULES_MODULE': '', 'CE_PHASED': '1'})

    def test_fresh_engines_do_not_leak_assumptions(self):
        first = self.solve(1, [['Greater', 'x', 0]])
        second = self.solve(['Abs', 'x'])
        self.assertEqual(first['status'], 'answer')
        self.assertEqual(second['status'], 'answer')
        import sympy as s
        x = s.Symbol('x', real=True)
        primitive = to_sympy(second['answer'], {'x': 'real'})
        self.assertEqual(s.diff(primitive, x).subs(x, -2), 2)

    def test_loggamma_decimal_and_contradiction(self):
        self.assertEqual(self.solve(['Digamma', 'x'])['answer'], ['LogGamma', 'x'])
        self.assertEqual(self.solve({'decimal': '0.125'})['status'], 'answer')
        self.assertEqual(self.solve(1, [['Greater', 'x', 0], ['Less', 'x', 0]])['status'], 'unsupported-assumptions')

    @unittest.skipUnless(os.environ.get('BENCH_TEST_CE_RULES_MODULE'), 'Optional pinned CE Rubi fixture')
    def test_real_rules_setup_is_separate_from_solving(self):
        case = {**build()[0], 'integrand': 1, 'assumptions': [], 'domains': {}}
        result = invoke_phased(['node', str(ROOT/'integral_benchmark/adapters/ce.mjs')],
            {'protocol_version': 2, 'case': case}, 120, 30,
            {'CE_MODULE': os.environ['BENCH_TEST_CE_MODULE'],
             'CE_RULES_MODULE': os.environ['BENCH_TEST_CE_RULES_MODULE'], 'CE_PHASED': '1',
             'CE_STEP_BUDGET': '300000', 'CE_RULE_TIME_MS': '30000'})
        self.assertEqual(result['status'], 'answer')
        self.assertEqual(result['answer'], 'x')
        self.assertGreater(result['setup']['rules']['rule_count'], 0)
        self.assertGreater(result['setup_wall_ms'], result['solver_ms'])
        print(json.dumps({'fixture': 'rubi-unit-integrand', 'setup_wall_ms': result['setup_wall_ms'],
                          'solve_wall_ms': result['solve_wall_ms'], 'solver_ms': result['solver_ms'],
                          'rules': result['setup']['rules']}))


if __name__ == '__main__': unittest.main()
