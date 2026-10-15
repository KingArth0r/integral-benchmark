// Semantic translations are independent of loading CE and testable without it.
const aliases = { Log: 'Ln', Si: 'SinIntegral', Ci: 'CosIntegral', Ei: 'ExpIntegralEi',
  Ceiling: 'Ceil', FractionalPartFloor: 'Fract',
  LambertW: 'ProductLog', Hypergeometric: 'HypergeometricPFQ', ExpIntegral: 'ExpIntegralE' };
const reverse = Object.fromEntries(Object.entries(aliases).map(([a, b]) => [b, a]));
const accepted = new Set(['Add', 'Subtract', 'Multiply', 'Divide', 'Rational', 'Negate', 'Power',
  'Complex', 'Tuple', 'Sin', 'Cos', 'Tan', 'Cot', 'Sec', 'Csc', 'Arcsin', 'Arccos', 'Arctan',
  'Arccot', 'Arcsec', 'Arccsc', 'Sinh', 'Cosh', 'Tanh', 'Coth', 'Sech', 'Csch', 'Arsinh',
  'Arcosh', 'Artanh', 'Arcoth', 'Arsech', 'Arcsch', 'Log', 'Exp', 'Sqrt', 'Abs', 'Erf',
  'Erfc', 'Erfi', 'Ei', 'Si', 'Ci', 'Gamma', 'Beta', 'Zeta', 'PolyLog', 'PolyGamma',
  'LambertW', 'BesselJ', 'BesselY', 'BesselI', 'BesselK', 'EllipticF', 'EllipticE',
  'EllipticK', 'EllipticPi', 'Floor', 'Ceiling', 'FractionalPartFloor', 'Sign', 'Min', 'Max', 'FresnelS', 'FresnelC',
  'Digamma', 'LogGamma', 'Which', 'And', 'Or', 'Not', 'Equal', 'NotEqual',
  'Less', 'LessEqual', 'Greater', 'GreaterEqual', 'Element']);

export function input(x) {
  if (Array.isArray(x)) {
    if (!accepted.has(x[0])) throw new Error(`Unsupported input operator ${x[0]}`);
    return [aliases[x[0]] ?? x[0], ...x.slice(1).map(input)];
  }
  if (x && typeof x === 'object') {
    if (Object.keys(x).length === 1 && 'decimal' in x) {
      const match = /^([+-]?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/.exec(x.decimal);
      if (!match) throw new Error('Invalid exact decimal');
      const scale = (match[3]?.length ?? 0) - Number(match[4] ?? 0);
      if (Math.abs(scale) > 10000) throw new Error('Exact decimal scale exceeds adapter limit');
      let numerator = BigInt((match[1] || '') + match[2] + (match[3] || ''));
      let denominator = 1n;
      if (scale > 0) denominator = 10n ** BigInt(scale);
      else numerator *= 10n ** BigInt(-scale);
      return ['Rational', { num: numerator.toString() }, { num: denominator.toString() }];
    }
    throw new Error('Unsupported input object');
  }
  if (typeof x === 'number' && !Number.isSafeInteger(x)) throw new Error('Integer exceeds JavaScript exact range');
  return x;
}

export function output(x) {
  // CE uses real odd roots on the negative real axis; never label these as
  // benchmark principal-complex Power/Root without preserving that distinction.
  if (Array.isArray(x)) return [({ Root: 'CERoot', Power: 'CEPower' })[x[0]] ?? reverse[x[0]] ?? x[0], ...x.slice(1).map(output)];
  if (x && typeof x === 'object') {
    if ('num' in x) {
      if (/^[+-]?\d+$/.test(String(x.num)) && Number.isSafeInteger(Number(x.num))) return Number(x.num);
      return { decimal: String(x.num) };
    }
    if ('sym' in x) return x.sym;
    if ('fn' in x) return output(x.fn);
    throw new Error('Unsupported CE result object');
  }
  if (typeof x === 'number' && !Number.isFinite(x)) throw new Error('Nonfinite numeric output');
  if (typeof x === 'number' && Number.isInteger(x) && !Number.isSafeInteger(x))
    throw new Error('Unsafe integer output; exact value not recoverable');
  if (typeof x === 'number' && !Number.isInteger(x)) return { decimal: String(x) };
  return x;
}

function rational(x) {
  if (Number.isSafeInteger(x)) return [BigInt(x), 1n];
  if (!Array.isArray(x)) return null;
  if (x[0] === 'Negate') {
    const value = rational(x[1]);
    return value && [-value[0], value[1]];
  }
  if (['Divide', 'Rational'].includes(x[0])) {
    const a = rational(x[1]), b = rational(x[2]);
    if (!a || !b || b[0] === 0n) return null;
    let p = a[0] * b[1], q = a[1] * b[0];
    if (q < 0n) { p = -p; q = -q; }
    let u = p < 0n ? -p : p, v = q;
    while (v) [u, v] = [v, u % v];
    return [p / u, q / u];
  }
  return null;
}

export function inputBranchWarnings(x, domains = {}) {
  const warnings = [];
  function visit(node) {
    if (!Array.isArray(node)) return;
    if (node[0] === 'Power') {
      const exp = rational(node[2]);
      // Parameter-dependent exponents and exact fractional exponents can hit
      // CE's real-odd-root convention. A positive literal base cannot.
      if (!(typeof node[1] === 'number' && node[1] > 0) &&
          !(typeof node[1] === 'string' && domains[node[1]] === 'positive') &&
          !(exp && (exp[1] === 1n || exp[1] % 2n === 0n)))
        warnings.push({ expression: node, restriction: 'base outside the negative real axis',
          reason: 'CE and principal powers may differ on negative real bases' });
    }
    node.slice(1).forEach(visit);
  }
  visit(x);
  return warnings;
}
