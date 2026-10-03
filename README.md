# Integral Benchmark

A solver-independent integration benchmark and coverage map for computer algebra
systems and AI systems. The goal is broad, auditable mathematical coverage, not
the largest count of superficially different exercises.

**Status: initial research release.** There is a 30-family coverage taxonomy,
an original 68-case pilot, a reproducible inventory of a pinned large upstream
corpus, CE and SymPy adapters, and a command protocol for other systems.
This is not yet a comprehensive gold-standard corpus or a CAS leaderboard.

Start with the [measured coverage map](reports/COVERAGE.md),
[methodology](docs/METHODOLOGY.md), [expansion plan](docs/ROADMAP.md), and
[source catalog](sources.json). The map explicitly retains unmeasured families.

## Run locally

Requires Python 3.11 or newer. From this checkout:

```sh
python -m venv .venv
# Activate .venv using your operating system's normal activation command.
python -m pip install -e .
python -m unittest discover -s tests -v
python -m integral_benchmark.cli seed
python -m integral_benchmark.cli run --engine sympy --output reports/local/sympy
```

SymPy 1.14.0 is pinned for both its adapter and the current verifier. For SymPy
results, the verifier is NOT independent of the solver implementation; this is
recorded in each run. Numeric checks are evidence, not mathematical proofs.

### Compute Engine

The current adapter loads a local CE source checkout so the exact Git revision
and dirty state can be recorded. Install that checkout's dependencies first.
Node 22 or newer and CE's `tsx` development dependency are required.

```sh
python -m integral_benchmark.cli run --engine ce --ce-root /path/to/compute-engine --timeout 30 --output reports/local/ce
```

For lower startup overhead, build that checkout into a fresh ESM bundle with its
bundler and pass `--ce-module /path/to/bundle.mjs`. The run records the bundle's
SHA-256 as well as the checkout revision. The caller is responsible for building
from that recorded revision. Do not use a stale release bundle and label it as
the current source. Bundled runs without `--rules` do not need the TypeScript loader.

Use `--rules` to load CE's optional Rubi integration rule pack as a separately
labeled configuration. Results without that flag measure the default integrator,
not every optional extension available in CE. The adapter never reads expected
answers. It exposes ordinary `Integrate`, supported closed contours, and explicit
whole-real-line principal values. It does not silently substitute a principal
value for an ordinary integral.

### Other CAS and AI systems

```sh
python -m integral_benchmark.cli run --engine my-cas --command-json '["my-cas-adapter", "--json"]' --output reports/local/my-cas
```

The executable receives one JSON request on stdin and writes one JSON response
on stdout. See [the adapter protocol](docs/PROTOCOL.md). Adapters for Wolfram,
Maple, Maxima, FriCAS, and Sage are planned, not claimed implemented. No commercial
software or credentials are bundled. AI-assisted and model-only runs must use
distinct engine identities and disclose tools, attempts, and resource budgets.

## Inventory and import the existing corpus

The [SymPy integration corpus](https://github.com/sympy/integration-test-suites)
is a valuable upstream resource. We inventory its actual records rather than
trusting README counts. It is not vendored into this repository.

```sh
git clone https://github.com/sympy/integration-test-suites.git .cache/upstream
git -C .cache/upstream checkout 871364f2923d6684d45470a91d7584ca162d0723
python -m integral_benchmark.cli inventory --upstream .cache/upstream --output reports/local/inventory --import-suite rubi --import-suite independent
```

Imports retain reference provenance and label answers `upstream-unreviewed`.
The safe expression translator does not execute Python or use `sympify` on source
text. Unsupported syntax is recorded, not dropped invisibly. Missing assumptions
are explicitly marked rather than invented. Import output is ignored by Git.

`--include-review` permits local imports of suites whose source permissions need
additional review. It is NOT a redistribution license. Read the upstream
per-suite licensing notes before publishing any derived corpus. Preserve all
applicable notices if you redistribute licensed material.

The upstream also has known omissions in its own import process; our inventory
counts only records present in the pinned checkout, not every original problem.

## Generate a coverage map

```sh
python -m integral_benchmark.cli report --inventory reports/local/inventory/inventory.json --run reports/local/ce --run reports/local/sympy --output reports/local/map
```

Both Markdown and machine-readable JSON are produced. Per-case logs preserve
timeouts, unsupported syntax, unresolved results, reference mismatches, and
verification failures. The corpus is not filtered to cases CE can already solve.
Use `--limit` for deterministic family-balanced pilot sampling, not leaderboard
claims. Every run records the selected IDs and corpus digest.

## Contribute

See [contribution rules](CONTRIBUTING.md). Useful contributions include audited
problems, domain/branch annotations, independent certificates, adapters, and
minimized counterexamples. Add new mathematical families, not just numerical
variants that inflate a score.

Original code and pilot fixtures are MIT licensed. Third-party corpus rights
remain separate. This project is not affiliated with or endorsed by the named
CAS vendors or contest organizers.
