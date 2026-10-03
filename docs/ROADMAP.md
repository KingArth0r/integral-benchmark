# Integral benchmark expansion plan

The objective is a comprehensive, independently auditable benchmark that guides
integration development across CAS implementations. The first release establishes
the measurement infrastructure; it does not claim that all known integrals have
been collected or that every answer can be automatically proved.

## First milestone

Deliver a reproducible source inventory, explicit mathematical taxonomy, safe
interchange format, bounded solver runner, initial CE and SymPy adapters,
conservative verifier, and measured pilot map. Keep the project independent of
CE's release cycle and avoid adding thousands of expensive cases to its unit tests.

## Build the audited core

Target 500 to 1000 reviewed cases spanning every single-variable family, with
balanced definite and indefinite sections and explicit negative cases. Include
parameter boundaries, removable singularities, branch discontinuities, endpoints,
real-axis poles, and cases where no elementary antiderivative exists but a special
function answer does. Record what answer classes are acceptable.

Maintain source manifests for MIT, Berkeley, HMMT, and JEE. Separate qualifying
rounds from finals, distinguish similarly named Berkeley contests, and preserve
whether a problem asks for the integral itself or a larger expression involving
it. Retain original PDFs or links and transcription checksums outside solver input.

## Expand the large corpus

Use the pinned upstream Rubi and independent collections as import inputs, not
unchecked ground truth. Audit their parameter assumptions and branch conventions.
Preserve unsupported syntax and upstream omissions as measurable acquisition gaps.
Add licensed or public-domain integral tables, special-function references, and
complex-analysis collections after source-specific permission review.

Prioritize missing families instead of multiplying easy templates. Generated
reverse-differentiation cases are useful but have a biased distribution; pair them
with independently constructed definite problems and adversarial near-misses.

## Expand solver and verification support

Add tested Wolfram, Maple, Maxima, FriCAS, and Sage adapters. Each must preserve
backend identity and settings and pass semantic translation tests. Add a second
independent verification engine and interval/error-bounded numerical checks.
Domain validity, convergence, parameter exceptions, and branch continuity need
their own evidence objects. A single universal answer-equivalence oracle is not
assumed available.

## Publish defensible comparisons

Freeze benchmark versions, publish per-case outcomes and denominators, and retain
source/family macro scores alongside raw counts. Maintain separate elementary,
special-function, numerical, convergence, contour, and AI-tool tracks. Establish
resource-controlled repeated timing before any speed leaderboard. Publish
counterexamples and uncertainty rather than forcing every result into pass/fail.

## Use failures to prioritize CE

Group failures by required capability: input representation, exact algebra,
identity recognition, integration algorithm, special-function support, assumptions,
limits/convergence, or verification. Confirm each diagnosis with a minimized
reproduction before opening an implementation task. An unverified answer is not
evidence that CE lacks the integration algorithm.
