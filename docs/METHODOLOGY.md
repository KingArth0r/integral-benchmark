# Integration benchmark methodology

The benchmark measures whether a specified mathematical problem is represented,
attempted, answered, and checked. These stages must remain distinguishable. A
large source inventory is not the same thing as a verified corpus, and a small
pilot does not establish general superiority over another system.

## Mathematical scope

The implemented protocol handles single-variable indefinite integrals, definite
integrals, explicit Cauchy principal values, and closed contours. Numerical,
non-elementarity, infinite-series, and multivariate tracks are coverage targets;
they do not yet have complete solvers and verification policies here.

Cases record expression trees, domains, assumptions, branch convention, bounds
or contour, provenance, and expected outcome. Arbitrary special functions are
not automatically acceptable answer wrappers. Answers containing unevaluated
integrals are unresolved. Conditional expressions need a condition-aware adapter
and verifier; the initial adapters report them separately.

Local antiderivative validity is distinct from a globally valid primitive.
For example, matching a derivative away from discontinuities does not justify
using the fundamental theorem across those discontinuities. No definite result
is constructed by the harness from unchecked endpoint substitution.

## Reference evidence

Original pilot references include a short mathematical rationale. They are
curated reference claims, not machine-checked formal proofs. Imported references
are unreviewed even when their upstream source reports an audit. Original source
and answer provenance should survive corrections; retain both the original claim
and the audited correction when developing a gold corpus.

The initial verifier checks symbolic derivative identities or equality to the
reference using SymPy, followed where appropriate by 40- and 70-digit residual
sampling. It never labels numerical agreement a proof. It does not yet prove
domain completeness, convergence, branch continuity, or parameter exhaustiveness.
It never arbitrarily substitutes parameters to turn a generic result into a proof.

| Verdict | Meaning |
|---|---|
| identity-checked | Symbolic derivative equality on the common differentiable domain |
| reference-match | Symbolic equality to a curated definite reference |
| reference-match-unreviewed | Equality to an imported reference that needs audit |
| classification-match | Explicit divergent or undefined status matches the curated case |
| safe-rejection | No finite value returned, but divergence was not explicitly identified |
| numerically-supported | Residual samples agree; not a proof |
| numeric-mismatch | Numerical counterexample candidate requiring domain/reference review |
| wrong | A finite answer contradicts a curated divergent or undefined problem |
| unverified | Evidence insufficient; this does not mean the answer is wrong |
| not-solved | No checkable answer or classification returned |
| verification-timeout | The checker exhausted its separate time budget |
| verifier-error | The checker failed; do not blame the solver |

The map's compact checked count includes the first, second, and fourth rows.
Publish the breakdown alongside it. Do not call it a formally certified success
rate. A future strict leaderboard must add domain and convergence certificates.

## Sampling and deduplication

Source counts retain all records. Structural deduplication renames only the
integration variable and includes domains, assumptions, bounds, contour, branch
convention, and ordinary versus PV semantics. It does not establish algebraic
equivalence. Near-duplicate families require a later, audited grouping stage.

Family inference is syntax-based and explicitly labeled heuristic. A trigonometric
integrand may be easiest to solve by residues or symmetry; the inferred family
does not claim to identify the required technique. Method tags should come from
reviewed solution evidence.

Use family-balanced scoring alongside raw coverage. All attempted cases remain
in the denominator, including unsupported inputs and timeouts. Report end-to-end
input coverage separately from mathematical solver coverage. Do not hide missing
families by reporting only what a system accepts.

The original pilot is public and hand-selected. It is not a statistically
representative random sample and is not contamination resistant. A future
holdout should split by mathematical template, maintain private generator seeds,
validate transformed domains, and include novel independently reviewed problems.
Changing constants alone does not create meaningful new reasoning challenges.

## Timing and resource policy

Each solver invocation is a fresh process with a hard parent-enforced wall
timeout. The wall budget includes interpreter startup, source loading, translation,
and computation. Adapters additionally report the time spent in their integration
entry point. Verification has a separate process and budget and is never included
in solver time.

Current worker processes do not launch descendants. External adapters must not
leave detached workers behind. This harness is not a security sandbox, does not
enforce a memory cap, and should only execute trusted adapter programs. Strong
container/job-object process-tree isolation and output-size limits are required
before running untrusted submissions on a shared service.

The published pilot uses one repetition and may use parallel jobs. It is suitable
for finding coverage gaps, NOT a speed ranking. Future performance comparisons
must use serial paired runs, repeated measurements, fixed CPU/memory limits,
runtime and engine versions, cold and warm modes, and results on both the full
case set and the intersection solved by all systems. Report solve-time curves
and timeout rates; do not compare each solver's own easy subset.

## Corpus rights and source omissions

Each source has an acquisition and redistribution status in `sources.json`.
Public availability is not treated as a blanket license. No bulk third-party
exercise collection is shipped in this release. The pinned upstream inventory
contains metadata, hashes, and omission reasons, not copied integrands or answers.

The upstream MIT transcription itself lists 38 omitted posted problems. Our
inventory cannot recover problems absent upstream. Similar upstream translation
limitations must stay visible when claiming collection coverage. Contest archives
need an audited year/round manifest, not just an assertion that all problems were
downloaded.
