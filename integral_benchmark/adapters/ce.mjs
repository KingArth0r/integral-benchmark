import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { performance } from 'node:perf_hooks';
import { input, output, inputBranchWarnings } from './ce-expressions.mjs';

// CE source or a published ESM bundle is selected externally, never from case data.
let ce;
function contains(x, names) {
  return Array.isArray(x) && (names.includes(x[0]) || x.slice(1).some(a => contains(a, names)));
}

let rulesReport;
async function solve(c) {
  if (c.kind === 'numerical') return { status: 'unsupported-kind' };
  const assume = predicate => {
    const status = ce.assume(predicate);
    if (!['ok', 'tautology'].includes(status)) throw new Error(`Assumption rejected: ${status}`);
  };
  // Domain assumptions must reach the solver, not just the answer checker.
  try {
    for (const [name, domain] of Object.entries(c.domains)) {
      if (domain === 'real') assume(['Element', name, 'RealNumbers']);
      else if (domain === 'positive') {
        assume(['Element', name, 'RealNumbers']);
        assume(['Greater', name, 0]);
      } else if (domain !== 'complex') return { status: 'unsupported-assumptions' };
    }
    for (const predicate of c.assumptions) assume(input(predicate));
  } catch (e) {
    return { status: 'unsupported-assumptions', reason: e.message };
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
  const common = { solver_ms, answer_text: JSON.stringify(answer),
    input_branch_warnings: inputBranchWarnings(c.integrand, c.domains) };
  if (contains(answer, ['Integrate', 'ContourIntegrate'])) return { ...common, status: 'unevaluated' };
  if (result.isNaN) return { ...common, status: 'undefined' };
  if (contains(answer, ['Error'])) return { ...common, status: 'error' };
  if (answer === 'PositiveInfinity' || answer === 'NegativeInfinity') return { ...common, status: 'divergent' };
  try {
    const translated = output(answer);
    if (contains(answer, ['ConditionalExpression'])) return { ...common,
      status: 'conditional', answer: translated,
      reason: 'Condition retained; not an unconditional answer' };
    return { ...common, status: 'answer', answer: translated };
  } catch (e) {
    return { ...common, status: 'answer-untranslated', reason: e.message };
  }
}

const phased = process.env.CE_PHASED === '1';
let ready = false;
try {
  const start = performance.now();
  const { ComputeEngine } = await import(pathToFileURL(process.env.CE_MODULE).href);
  ce = new ComputeEngine();
  if (process.env.CE_RULES_MODULE) {
    const { loadIntegrationRules } = await import(pathToFileURL(process.env.CE_RULES_MODULE).href);
    const rulesStart = performance.now();
    const options = { stepBudget: Number(process.env.CE_STEP_BUDGET ?? 300000),
      timeLimitMs: Number(process.env.CE_RULE_TIME_MS ?? 120000) };
    const report = loadIntegrationRules(ce, options);
    rulesReport = { rule_count: report.ruleCount, skipped: report.skipped,
      skipped_rules: report.skippedRules, load_ms: performance.now() - rulesStart, options };
  }
  // Compile before case-specific assumptions. Never reuse this engine for another case.
  if (phased) console.log(JSON.stringify({ event: 'ready', initialization_ms: performance.now() - start,
    ...(rulesReport ? { rules: rulesReport } : {}) }));
  ready = true;
  const request = JSON.parse(readFileSync(0, 'utf8'));
  const result = await solve(request.case);
  const response = { ...result, ...(rulesReport ? { rules: rulesReport } : {}) };
  console.log(JSON.stringify(phased ? { event: 'result', result: response } : response));
} catch (e) {
  const result = { status: 'error', reason: `${e.name}: ${e.message}`,
    ...(rulesReport ? { rules: rulesReport } : {}) };
  console.log(JSON.stringify(phased ? (ready ? { event: 'result', result } :
    { event: 'setup-error', reason: result.reason }) : result));
}
