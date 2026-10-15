# Solver adapter protocol

Adapters are trusted executables invoked without a shell. Each process accepts
one UTF-8 JSON object on stdin and returns exactly one JSON object on stdout.
Diagnostic logs belong on stderr. A new process is used for each case.

CE uses protocol version 2: one `ready` JSON line after engine/rule loading,
then one `result` line containing the usual response object, then process exit.
The parent independently enforces setup and solve deadlines. It preserves setup
metadata even when the solve times out. No engine, assumption context, or compiled
rule binding is shared between cases. Other adapters retain version 1.

## Request

```json
{
  "protocol_version": 1,
  "case": {
    "schema_version": 1,
    "id": "example",
    "kind": "definite",
    "integrand": ["Divide", 1, ["Add", 1, ["Power", "x", 2]]],
    "variable": "x",
    "domains": {"x": "real"},
    "assumptions": [],
    "branches": "principal",
    "bounds": [["Negate", "PositiveInfinity"], "PositiveInfinity"]
  }
}
```

The request excludes expected answers, reference rationales, source solutions,
verification sample points, and family labels. IDs remain for correlation; a
future blind evaluation service should replace public IDs with opaque run IDs.

## Expressions

Integers are exact JSON integers. Rational numbers use `["Rational", p, q]`.
Decimals use `{"decimal":"0.125"}` and mean the exact decimal value, not an
unspecified floating-point approximation. Symbols are strings; built-in constants
include `Pi`, `ExponentialE`, `ImaginaryUnit`, and `PositiveInfinity`.

Functions use prefix arrays, such as `["Sin","x"]`. `Log` means the natural
logarithm. Elliptic functions use the parameter m, not the modulus k. Ordinary
`Power` has the principal complex convention; real roots must use `RealRoot`.
An adapter must explicitly reject unsupported translations rather than invent a
function or silently change branch conventions. The reference implementation's
operator allowlist is in `expressions.py`.

CE output `Root` and `Power` are exported as `CERoot` and `CEPower`, not assumed
identical to principal-complex powers: CE uses real odd roots on negative real
inputs. The verifier translates known domains exactly. Unknown branch domains
can receive only `identity-checked-restricted`, with the excluded negative real
axis recorded. This is not included in the ordinary checked count. Fractional or
symbolic powers in CE input also carry branch-review warnings. An integral that
lost branch information while simplifying must not silently become a global pass.
`LogGamma` is the analytic log-gamma, distinct from principal `Log(Gamma(x))`.

Explicit assumptions use expression trees, not executable strings. CE accepts
only predicates its assumption API reports as accepted/redundant; rejected or
contradictory assumptions produce `unsupported-assumptions`. The independent
verifier supports scalar symbol/finite-constant inequalities and non-equality,
including conjunctions, and refuses other predicates. Parameter exceptional
values and global domain completeness remain uncertified even after a local
derivative identity. Conditional answers retain their expression and conditions
and receive `conditional-unverified`, never unconditional credit.

This small language is similar to MathJSON but is an independent benchmark
contract. In particular CE's `Ln` is mapped to benchmark `Log` explicitly.

`FractionalPartFloor(x)` explicitly means the real floor-based fractional part
`x-Floor(x)` in [0,1), including for negative x. It maps to CE `Fract` and SymPy
`frac`, NOT directly to Wolfram's signed `FractionalPart`. For instance its value
at -5/4 is 3/4. Benchmark `Ceiling` maps to CE `Ceil`. `Which` cases, when present,
have alternating condition/value operands with first-true semantics; adapters
that cannot translate their predicates must report a translation error.

## Response

```json
{"status":"answer","answer":"Pi","solver_ms":12.5,"engine_version":"example-version"}
```

Supported statuses are `answer`, `answer-untranslated`, `unevaluated`,
`conditional`, `divergent`, `undefined`, `unsupported-kind`,
`unsupported-assumptions`, `translation-error`, and `error`.
An `answer` requires an expression tree. Returning an exact expression is distinct
from claiming a numerical approximation; numerical tracks need a separate
accuracy/error-bound contract before implementation.

The harness adds `timeout`, `launch-error`, `process-error`, or `protocol-error`
when appropriate. Optional `reason`, `native_status`, and `answer_text` preserve
diagnostics. Never return `divergent` merely because a solver returned its input.

Protocol 2 additionally distinguishes `setup-timeout` and `setup-error` from
solver failure. Setup/protocol/process failures receive `infrastructure-error`;
three consecutive infrastructure errors stop the queue after saving evidence.
`setup_wall_ms`, `solve_wall_ms`, engine-reported `solver_ms`, total `wall_ms`, and
verification time are separate measurements. Solve wall time includes translation,
assumptions, integration, serialization, and process exit. It is not warm throughput.
Never infer Cauchy principal value semantics unless `kind` explicitly requests it.

Adapters should report exact engine/backend version, settings, and solver time.
Sage backed by Maxima is not an independent implementation of Maxima. An AI using
Wolfram tools is a tool-assisted system and must not be labeled model-only.

## Adapter checklist

- Translate assumptions and domains or explicitly reject them.
- Test exact rationals, large integers, log conventions, and real roots.
- Test a nontrivial branch-sensitive expression in both directions.
- Preserve unevaluated and conditional results.
- Distinguish ordinary divergence from a finite principal value.
- Keep initialization, solving, serialization, and verification measurements separate.
- Run roundtrip tests and a known correct/incorrect adversarial fixture set.
- Do not spawn detached descendants; the harness is not an untrusted-code sandbox.
