import json
from pathlib import Path
import shutil
import subprocess
import unittest
from integral_benchmark.expressions import parse, to_sympy, from_sympy
from integral_benchmark.model import load_cases, infer_family, ROOT
from scripts.discrete_cases import build


class Discrete(unittest.TestCase):
    def test_floor_fractional_part_negative(self):
        import sympy as s
        self.assertEqual(to_sympy(parse('frac(-5/4)')), s.Rational(3,4))
        f = to_sympy(parse('frac(x)'), {'x':'real'})
        self.assertEqual(to_sympy(from_sympy(f), {'x':'real'}), f)

    def test_classification(self):
        self.assertEqual(infer_family(parse('frac(x)')), 'piecewise-discrete')
        self.assertEqual(infer_family(parse('Max(x,1-x)')), 'piecewise-absolute')

    def test_case_generation_matches_saved_corpus(self):
        cases = build()
        self.assertEqual(len(cases), 20)
        self.assertEqual(load_cases(ROOT / 'corpus/discrete-regressions.jsonl'), cases)

    def test_floor_primitive_negative_bounds(self):
        import sympy as s
        def primitive(x):
            n=s.floor(x)
            return x*n-n*(n+1)/2
        self.assertEqual(primitive(s.Rational(3,2))-primitive(s.Rational(-3,2)), -s.Rational(3,2))
        self.assertEqual(primitive(s.Integer(3))-primitive(s.Integer(0)), 3)

    @unittest.skipUnless(shutil.which('node'), 'Node required for CE adapter translation test')
    def test_ce_roundtrip_semantics_without_loading_ce(self):
        module = (ROOT/'integral_benchmark/adapters/ce-expressions.mjs').as_uri()
        code = f'''import {{input,output}} from {json.dumps(module)};
          import assert from "node:assert/strict";
          assert.deepEqual(input(["Ceiling","x"]), ["Ceil","x"]);
          assert.deepEqual(input(["FractionalPartFloor",["Rational",-5,4]]), ["Fract",["Rational",-5,4]]);
          assert.deepEqual(output(["Fract","x"]), ["FractionalPartFloor","x"]);
          assert.deepEqual(output(["Ceil","x"]), ["Ceiling","x"]);
          assert.throws(()=>input(["FractionalPart","x"]));
          assert.throws(()=>input(["Unknown","x"]));
        '''
        subprocess.run(['node','--input-type=module','-e',code],check=True,capture_output=True,timeout=10)


if __name__ == '__main__': unittest.main()
