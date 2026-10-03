import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { performance } from 'node:perf_hooks';

// CE source or a published ESM bundle is selected externally, never from case data.
const { ComputeEngine } = await import(pathToFileURL(process.env.CE_MODULE).href);
const aliases = { Log: 'Ln', Si: 'SinIntegral', Ci: 'CosIntegral', Ei: 'ExpIntegralEi',
  LambertW: 'ProductLog', Hypergeometric: 'HypergeometricPFQ',
  ExpIntegral: 'ExpIntegralE' };
const reverse = Object.fromEntries(Object.entries(aliases).map(([a, b]) => [b, a]));
const accepted = new Set(['Add', 'Subtract', 'Multiply', 'Divide', 'Rational', 'Negate', 'Power',
  'Complex', 'Tuple', 'Sin', 'Cos', 'Tan', 'Cot', 'Sec', 'Csc', 'Arcsin', 'Arccos', 'Arctan',
  'Arccot', 'Arcsec', 'Arccsc', 'Sinh', 'Cosh', 'Tanh', 'Coth', 'Sech', 'Csch', 'Arsinh',
  'Arcosh', 'Artanh', 'Arcoth', 'Arsech', 'Arcsch', 'Log', 'Exp', 'Sqrt', 'Abs', 'Erf',
  'Erfc', 'Erfi', 'Ei', 'Si', 'Ci', 'Gamma', 'Beta', 'Zeta', 'PolyLog', 'PolyGamma',
  'LambertW', 'BesselJ', 'BesselY', 'BesselI', 'BesselK', 'EllipticF', 'EllipticE',
  'EllipticK', 'EllipticPi', 'Floor', 'Ceiling', 'Sign', 'Min', 'Max', 'FresnelS', 'FresnelC']);

function input(x) {
  if (Array.isArray(x)) {
    if (!accepted.has(x[0])) throw new Error(`Unsupported input operator ${x[0]}`);
    return [aliases[x[0]] ?? x[0], ...x.slice(1).map(input)];
  }
  if (x && typeof x === 'object') {
    if ('decimal' in x) throw new Error('Exact decimal input not implemented in CE adapter');
    throw new Error('Unsupported input object');
  }
  if (typeof x === 'number' && !Number.isSafeInteger(x)) throw new Error('Integer exceeds JavaScript exact range');
  return x;
}
function output(x) {
  if (Array.isArray(x)) return [reverse[x[0]] ?? x[0], ...x.slice(1).map(output)];
  if (x && typeof x === 'object') {
    if ('num' in x) {
      if (/^[+-]?\d+$/.test(String(x.num)) && Number.isSafeInteger(Number(x.num))) return Number(x.num);
      return { decimal: String(x.num) };
    }
    if ('sym' in x) return x.sym;
    if ('fn' in x) return output(x.fn);
    throw new Error('Unsupported CE result object');
  }
  if (typeof x === 'number' && !Number.isInteger(x)) return { decimal: String(x) };
  return x;
}
function contains(x, names) {
  return Array.isArray(x) && (names.includes(x[0]) || x.slice(1).some(a => contains(a, names)));
}

async function solve(c) {
  if (c.assumptions.length) return { status: 'unsupported-assumptions' };
  if (c.kind === 'numerical') return { status: 'unsupported-kind' };
  const ce = new ComputeEngine();
  // Domain assumptions must reach the solver, not just the answer checker.
  for (const [name, domain] of Object.entries(c.domains)) {
    if (domain === 'real') ce.assume(['Element', name, 'RealNumbers']);
    else if (domain === 'positive') {
      ce.assume(['Element', name, 'RealNumbers']);
      ce.assume(['Greater', name, 0]);
    } else if (domain !== 'complex') return { status: 'unsupported-assumptions' };
  }
  if (process.env.CE_RULES_MODULE) {
    const { loadIntegrationRules } = await import(pathToFileURL(process.env.CE_RULES_MODULE).href);
    loadIntegrationRules(ce);
  }
  let f, bounds;
  try { f = input(c.integrand); bounds = c.bounds?.map(input); }
  catch (e) { return { status: 'translation-error', reason: e.message }; }
  const boxed = ce.box(f);
  if (boxed.isValid === false) return { status: 'translation-error', reason: JSON.stringify(boxed.json) };
  const start = performance.now();
  let result, report;
  if (c.kind === 'contour') {
    const contour = { ...c.contour };
    for (const key of ['center', 'radius', 'lowerLeft', 'upperRight']) {
      if (key in contour) contour[key] = input(contour[key]);
    }
    if (contour.vertices) contour.vertices = contour.vertices.map(input);
    report = ce.contourIntegrate(f, c.variable, contour);
  } else if (c.kind === 'principal-value') {
    if (JSON.stringify(bounds) !== JSON.stringify([['Negate', 'PositiveInfinity'], 'PositiveInfinity']))
      return { status: 'unsupported-kind', reason: 'CE adapter currently exposes whole-real-line PV only' };
    report = ce.contourIntegrate(f, c.variable, { kind: 'real-line', principalValue: true });
  } else {
    result = ce.box(['Integrate', f, bounds ? ['Tuple', c.variable, ...bounds] : c.variable]).evaluate();
  }
  const solver_ms = performance.now() - start;
  if (report) {
    if (report.status !== 'success') return {
      status: report.status === 'pole-on-contour' ? 'undefined' : 'unevaluated',
      solver_ms, native_status: report.status, reason: report.reason,
    };
    result = report.value;
  }
  const answer = result.json;
  const common = { solver_ms, answer_text: JSON.stringify(answer) };
  if (contains(answer, ['Integrate', 'ContourIntegrate'])) return { ...common, status: 'unevaluated' };
  if (result.isNaN) return { ...common, status: 'undefined' };
  if (contains(answer, ['Error'])) return { ...common, status: 'error' };
  if (answer === 'PositiveInfinity' || answer === 'NegativeInfinity') return { ...common, status: 'divergent' };
  return { ...common, status: 'answer', answer: output(answer) };
}

try {
  const request = JSON.parse(readFileSync(0, 'utf8'));
  console.log(JSON.stringify(await solve(request.case)));
} catch (e) {
  console.log(JSON.stringify({ status: 'error', reason: `${e.name}: ${e.message}` }));
}
