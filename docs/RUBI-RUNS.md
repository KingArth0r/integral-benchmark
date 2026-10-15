# Resumable Rubi coverage runs

The full pinned Rubi suite has 64,740 source records. The importer can currently
represent 64,718 integrands; 22 translation failures remain in the inventory.
These are acquisition or representation gaps, not successful integrals and not
solver failures. Every translated record remains selected, including duplicates,
missing references, and parameterized problems. The imported corpus is not a
reviewed gold set: 57,547 runnable problems have parameters whose assumptions
were not reconstructed from the original source.

## Configurations

Keep default CE, CE with its bundled Rubi port, and upstream Rubi as distinct
engines. At CE revision `1dc4f0864ad3c79fd11c5970ee08507c4a0e3288`, the optional
loader compiled 6,574 rules with zero skips. This does not imply full upstream
coverage. It includes algebraic, exponential, logarithmic, inverse trigonometric,
hyperbolic, inverse hyperbolic, selected trigonometric sections, and a polylogarithm
section. The adapter records actual load counts, skips, and loading time per case.

Build both ESM bundles from the same clean CE checkout using its installed
esbuild. The initial bundles used esbuild 0.28.2:

```sh
node node_modules/esbuild/bin/esbuild src/compute-engine/index.ts --bundle --platform=node --format=esm --outfile=/path/to/benchmark/.cache/ce-current.mjs
node node_modules/esbuild/bin/esbuild src/integration-rules.ts --bundle --platform=node --format=esm --outfile=/path/to/benchmark/.cache/ce-rules-current.mjs
```

## Pilot and full corpus

For new full baselines use the paired launcher below. The older single-run
commands in this section document the historical queue, not current settings.

```sh
python -m integral_benchmark.full_baseline --corpus reports/local/rubi-import/imported/rubi.jsonl --inventory reports/local/rubi-import/inventory.json --expected-count 64718 --ce-root /path/to/pinned-clean-ce --ce-module /path/to/ce.mjs --ce-rules-module /path/to/ce-rules.mjs --jobs 3 --timeout 120 --setup-timeout 120 --verify-timeout 20 --output reports/local/full-baseline-v2
```

This selects **every** imported case twice: default CE and CE with bundled Rubi.
There are no `--limit` or `--batch-size` options. It verifies that runnable cases
plus input translation failures account for all source records and that every
case names the same source revision. Run directories are `ce` and `ce-rubi`;
`baseline.json` tracks the paired run. `--jobs 3` means six solver/verifier jobs
across the pair, not three total. Both configurations use the same solve budget.
Rubi's explicit step budget defaults to 300,000 and its guard matches the solve
budget. An external hard deadline still terminates uncooperative engine code.

Run this as a long-lived process with stdout/stderr saved. The computer must stay
awake. To resume after interruption, repeat the **identical** command with
`--resume`. Use a dedicated pinned checkout and bundles so unrelated CE development
does not alter resume identity. The launcher makes the final coverage report only
after both configurations have recorded every runnable case. It never treats a
partial prefix as a full score. Source inventory failures remain a separate gap.

The setup budget is separate from solving; rule compilation is still per-case.
This intentionally pays a cold-start cost to prevent assumption/type/binding
contamination. Reusing a CE instance without a proven complete reset would change
the benchmark semantics. Do not market this as a warm-throughput benchmark.

Full baselines do not make the imported corpus a gold set. Assumptions review,
parameter exceptions, conditional results and branch-restricted identities are
recorded separately. `Root`/`Power` and `LogGamma` conventions are described in
[the protocol](PROTOCOL.md). No output is automatically declared a CE bug merely
because independent verification failed or timed out.

### Optional faster verification

Add `--verifier-mode warm --verifier-recycle 100` to a **new** full baseline.
Each runner thread then owns one reusable verifier process. SymPy is imported
once per worker, and its global assumptions and registered symbolic caches are
cleared before and after every case. Each request still has its own deadline;
a timeout, crash without a response, or invalid result discards the worker.
Workers also recycle after the configured number of cases. There is no answer
cache, no duplicate-case skipping, and no solver-engine reuse.

Fresh-process verification remains the default and the strongest isolation
reference. Warm mode reuses interpreter/module state and is explicitly labelled
in run metadata; tests establish parity for the documented regression fixtures,
not every possible SymPy expression. Startup is charged to the request needing
the worker, including after recycling. Changing this mode or recycling interval
changes the run fingerprint: never resume a fresh-mode journal as a warm run.
The already-running `53946ae` baseline remains pinned to fresh mode.

Paired runs now parse and validate the corpus once, share that read-only snapshot
between the two configurations and final report, and reuse its digest. Input is
read line-by-line instead of keeping a second corpus-sized string plus split-line
list in memory. Every source ID still has independent solver and verifier evidence.

Measure startup with `python -m scripts.profile_runner --run /path/to/ce --run
/path/to/ce-rubi --repeats 6 --output /path/to/profile.json`. It reads every complete
journal record available at inspection and times a synthetic derivative check;
it does not select or run a coverage sample. Partial-prefix timings must not be
extrapolated into a full-corpus score or advertised as a CAS speed ranking.

From the benchmark checkout, with its Python dependencies installed:

```sh
python -m integral_benchmark.cli run --engine ce --ce-root /path/to/ce --ce-module .cache/ce-current.mjs --rules --ce-rules-module .cache/ce-rules-current.mjs --timeout 30 --verify-timeout 20 --jobs 2 --output reports/pilot-ce-rubi
python -m integral_benchmark.cli inventory --upstream /path/to/pinned/upstream --output reports/local/rubi-import --import-suite rubi
python -m integral_benchmark.cli run --corpus reports/local/rubi-import/imported/rubi.jsonl --engine ce --ce-root /path/to/ce --ce-module .cache/ce-current.mjs --rules --ce-rules-module .cache/ce-rules-current.mjs --timeout 30 --verify-timeout 20 --jobs 2 --batch-size 128 --output reports/local/rubi-ce-full
```

Pin upstream to `871364f2923d6684d45470a91d7584ca162d0723`. To continue,
repeat the full-corpus command with `--resume`. `--batch-size` limits only NEW
work in that invocation, not the benchmark denominator. Omitting it runs every
remaining case. `--limit` instead chooses a smaller, family-balanced sample and
must not be presented as full-source execution.

## Checkpoints and interpretation

`results.jsonl` is an append-only evidence journal, flushed and synchronized after
each case. `progress.json` is a small atomically replaced progress summary.
`run.json` preserves the complete selected IDs, corpus digest, engine revision,
bundle digests, Python and Node versions, harness digest, budgets, and status.
Only one process may write a run directory. A terminated process releases its OS
lock; the remaining lock file is harmless. Resumption checks configuration,
duplicate IDs, membership, and case hashes before appending. Malformed journals
are rejected for explicit recovery; they are never silently truncated.

A resume skips all recorded outcomes, including timeouts and failures. To retry
with a larger budget or changed solver, use a new run directory. Do not edit the
adapter, verifier, corpus, bundles, or source checkout during an active run.

Fresh solver processes reload and compile Rubi for each case. Historical runs
included compilation in their process budget; new protocol-2 runs have a separate
setup budget. Full execution can take days; watch actual progress rather than
extrapolating integration-only timings. No speed ranking is warranted.

The full queue follows source order, so partial counts are not representative
scores. Report completed, remaining, and translation-failed counts separately.
Symbolic derivative checks establish identities only on the common differentiable
domain; unknown assumptions and branch completeness remain separate obligations.
Never convert verification timeouts or translation errors into mathematical bugs.
