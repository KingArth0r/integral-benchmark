# Contributing to Integral Benchmark

Changes should improve mathematical breadth, evidence quality, or reproducibility.
Do not optimize a score by omitting unsupported inputs or merging ordinary
integrals with principal values.

## Cases

Provide the exact source, problem identifier, domain, assumptions, branch
convention, integral semantics, reference provenance, and redistribution status.
Prefer original or clearly licensed material. Do not bulk-copy a book or contest
archive merely because it is downloadable. Keep imported corpora out of commits
until their rights and notices have been reviewed.

For a claimed correction, preserve the original reference and provide a derivation
or independently reproducible counterexample. Do not replace a disputed answer
just because one CAS produced a different expression. Check one-sided limits and
all exceptional parameter values before asserting convergence.

## Code and adapters

Run `python -m unittest discover -s tests -v`. Keep the core inventory and protocol
independent of any CAS. Never execute expression strings from a corpus. Adapters
may call trusted locally installed engines but must not receive expected answers.
Declare unimplemented translations and preserve conditions instead of guessing.

Test all new output classifications. Add regression cases for hangs, invalid
input, branch ambiguities, and false finite answers. If a verifier cannot decide,
retain an inconclusive verdict.

## Published results

Commit the corpus revision, selected case IDs, solver identity and settings,
resource budgets, and per-case outcomes. Sanitize local paths and secrets. Report
sampling bias and same-engine verification. Do not publish a speed ranking from
single parallel pilot runs.

## AI assistance

The initial implementation and original pilot were produced with AI assistance
and tested locally. New AI-assisted transcriptions require the same mathematical
and source review as human transcriptions. AI model/tool identities belong in
evaluation metadata, not in unqualified claims of mathematical proof.
