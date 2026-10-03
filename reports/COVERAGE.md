# Integral Benchmark coverage map

This map separates source inventory, runnable pilot coverage, and observed solver outcomes. It is not a ranking of overall CAS capability. Zero cases means an unmeasured gap, not solver failure.

## Source inventory

Pinned upstream revision: `871364f2923d6684d45470a91d7584ca162d0723`. Raw records: 80,873. Structurally unique translated problems: 79,146. Duplicate records among translated problems: 1,667.

Counts below classify integrand syntax, not the functions appearing in answers or required solution methods. Semantic families are marked Not classified because the inventory does not yet infer those properties. Imported assumptions and reference answers need further review.

| Suite | Raw | Definite | Translation failures | Redistribution status |
|---|---:|---:|---:|---|
| rubi | 64,740 | 0 | 22 | upstream-MIT |
| independent | 1,778 | 0 | 0 | upstream-MIT |
| hebisch | 10,335 | 0 | 0 | permission-review |
| blake | 3,154 | 0 | 13 | permission-review |
| mit_bee | 322 | 0 | 0 | permission-review |
| mit_bee_official | 544 | 262 | 25 | unlicensed-source-review |

## Measured family coverage

Each engine cell is **checked / attempted**. Checked means a derivative identity, equality to a curated reference, or an explicit classification match. These are different evidence levels, not formal global proofs. Numerical support and safe rejection are reported separately below and excluded from this count. All attempted cases remain in the denominator.

| Family | Inventory records | Pilot cases | ce | sympy |
|---|---:|---:|---:|---:|
| Polynomials and rational functions | 130 | 6 | 4 / 6 | 6 / 6 |
| General algebraic powers | 18,937 | 1 | 1 / 1 | 1 / 1 |
| Radicals and real roots | 7,926 | 3 | 3 / 3 | 3 / 3 |
| Pseudo elliptic and higher algebraic integrals | 3,141 | 0 | Not measured | Not measured |
| Exponential functions | 512 | 3 | 3 / 3 | 3 / 3 |
| Logarithmic functions | 3,179 | 2 | 2 / 2 | 2 / 2 |
| Nested exponential and logarithmic towers | 10,367 | 2 | 1 / 2 | 2 / 2 |
| Trigonometric functions | 23,093 | 4 | 4 / 4 | 4 / 4 |
| Inverse trigonometric functions | 3,170 | 2 | 2 / 2 | 2 / 2 |
| Hyperbolic functions | 5,166 | 2 | 2 / 2 | 2 / 2 |
| Inverse hyperbolic functions | 4,515 | 1 | 1 / 1 | 1 / 1 |
| Absolute values and piecewise functions | 11 | 2 | 2 / 2 | 1 / 2 |
| Floor ceiling and discrete structure | 30 | 1 | 0 / 1 | 0 / 1 |
| Gamma beta and zeta functions | 14 | 4 | 2 / 4 | 2 / 4 |
| Hypergeometric functions and polylogarithms | 222 | 2 | 0 / 2 | 1 / 2 |
| Elliptic integrals | 0 | 2 | 0 / 2 | 2 / 2 |
| Bessel functions | 0 | 1 | 0 / 1 | 1 / 1 |
| Other special functions | 400 | 3 | 2 / 3 | 3 / 3 |
| Definite integral symmetry | Not classified | 2 | 2 / 2 | 2 / 2 |
| Endpoint and interior singularities | Not classified | 6 | 3 / 6 | 4 / 6 |
| Infinite intervals and oscillation | Not classified | 7 | 7 / 7 | 6 / 7 |
| Cauchy principal values | Not classified | 3 | 0 / 3 | 2 / 3 |
| Meromorphic contour integrals | Not classified | 7 | 7 / 7 | 0 / 7 |
| Essential singularities | Not classified | 2 | 2 / 2 | 0 / 2 |
| Branch cut contour integrals | Not classified | 0 | Not measured | Not measured |
| Parameter dependent convergence and exceptional values | Not classified | 0 | Not measured | Not measured |
| Infinite series products and nested expressions | Not classified | 0 | Not measured | Not measured |
| Non elementary antiderivative decisions | Not classified | 0 | Not measured | Not measured |
| Multiple integrals | Not classified | 0 | Not measured | Not measured |
| Numerical accuracy and stability | Not classified | 0 | Not measured | Not measured |

## Evidence and failure breakdown

### ce

| Verdict | Cases |
|---|---:|
| classification-match | 4 |
| identity-checked | 24 |
| not-solved | 13 |
| numerically-supported | 3 |
| reference-match | 22 |
| safe-rejection | 2 |

| Solver or adapter outcome | Cases |
|---|---:|
| answer | 49 |
| divergent | 3 |
| undefined | 3 |
| unevaluated | 11 |
| unsupported-kind | 2 |

Engine identity: `{"dirty": false, "load_mode": "caller-built-bundle", "module_sha256": "06c584ffb6a3d5e5dd5563d9e9adacc7a7e10aacad01a886bbd17dc6f3aa6a56", "revision": "1dc4f0864ad3c79fd11c5970ee08507c4a0e3288", "rules": false, "runtime": "v22.14.0"}`. Budget 30.0 seconds per fresh solver process, 20.0 seconds per verifier; 1 parallel jobs. Verifier independent of solver engine: True.

Cases requiring follow-up are not automatically solver bugs. An unsupported kind can be an adapter limitation, and a numerical-only check can be a verifier limitation.

| Case | Solver outcome | Verification |
|---|---|---|
| pilot:reciprocal | answer | numerically-supported |
| pilot:partial-fractions | answer | numerically-supported |
| pilot:nested-exp | unevaluated | not-solved |
| pilot:erf | unevaluated | not-solved |
| pilot:polylog | unevaluated | not-solved |
| pilot:elliptic | unevaluated | not-solved |
| pilot:bessel | unevaluated | not-solved |
| pilot:digamma | unevaluated | not-solved |
| pilot:floor-finite | unevaluated | not-solved |
| pilot:endpoint-log | unevaluated | not-solved |
| pilot:zeta-moment | unevaluated | not-solved |
| pilot:dilog-value | unevaluated | not-solved |
| pilot:elliptic-complete | unevaluated | not-solved |
| pilot:cubic-cos-divergence | undefined | safe-rejection |
| pilot:interior-pole | undefined | safe-rejection |
| pilot:pv-simple | unsupported-kind | not-solved |
| pilot:pv-cos-cubic | answer | numerically-supported |
| pilot:pv-double-diverges | unsupported-kind | not-solved |

### sympy

| Verdict | Cases |
|---|---:|
| classification-match | 4 |
| identity-checked | 29 |
| not-solved | 16 |
| numerically-supported | 1 |
| reference-match | 17 |
| safe-rejection | 1 |

| Solver or adapter outcome | Cases |
|---|---:|
| answer | 47 |
| answer-untranslated | 1 |
| conditional | 1 |
| divergent | 4 |
| undefined | 1 |
| unevaluated | 5 |
| unsupported-kind | 9 |

Engine identity: `{"version": "1.14.0"}`. Budget 30.0 seconds per fresh solver process, 20.0 seconds per verifier; 1 parallel jobs. Verifier independent of solver engine: False.

Cases requiring follow-up are not automatically solver bugs. An unsupported kind can be an adapter limitation, and a numerical-only check can be a verifier limitation.

| Case | Solver outcome | Verification |
|---|---|---|
| pilot:absolute | conditional | not-solved |
| pilot:polylog | answer-untranslated | not-solved |
| pilot:digamma | unevaluated | not-solved |
| pilot:floor-finite | unevaluated | not-solved |
| pilot:fourier-lorentz | answer | numerically-supported |
| pilot:zeta-moment | unevaluated | not-solved |
| pilot:cubic-cos-divergence | unevaluated | not-solved |
| pilot:interior-pole | undefined | safe-rejection |
| pilot:pv-cos-cubic | unevaluated | not-solved |
| pilot:circle-no-poles | unsupported-kind | not-solved |
| pilot:circle-one | unsupported-kind | not-solved |
| pilot:circle-multiple | unsupported-kind | not-solved |
| pilot:circle-outside | unsupported-kind | not-solved |
| pilot:circle-clockwise | unsupported-kind | not-solved |
| pilot:circle-boundary | unsupported-kind | not-solved |
| pilot:circle-double | unsupported-kind | not-solved |
| pilot:circle-essential | unsupported-kind | not-solved |
| pilot:circle-essential-times | unsupported-kind | not-solved |

## Next coverage targets

1. Audit parameter domains and branches before treating the large imported corpus as a gold set.
2. Add source-reviewed Berkeley, HMMT, and JEE cases; retain exact year, round, and problem identifiers.
3. Expand definite integrals, parameter boundaries, divergent near-misses, and branch-cut contours.
4. Add numerical, non-elementarity, infinite-series, and multivariate protocols before scoring those tracks.
5. Add tested adapters for Wolfram, Maple, Maxima, FriCAS, and Sage with explicit backend identities.
6. Add domain-completeness certificates and independent reference audits; preserve inconclusive verdicts.
7. Run paired, repeated, serial performance trials before publishing speed comparisons.

The pilot is intentionally small and publicly visible. No contamination-resistant holdout exists yet. Case data and verification budgets are versioned; increasing either can change the map.
