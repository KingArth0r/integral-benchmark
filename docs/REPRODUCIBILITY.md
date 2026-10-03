# Reproducing the initial coverage map

The map combines an upstream source inventory with runs of the original pilot.
It does not claim that the entire upstream corpus was executed against either
engine. Source inventory and solver measurements have different denominators.

## Recorded inputs

- Upstream corpus revision: `871364f2923d6684d45470a91d7584ca162d0723`.
- CE checkout revision: `1dc4f0864ad3c79fd11c5970ee08507c4a0e3288`.
- CE configuration: default integrator, without the optional Rubi rule pack.
- Node runtime: 22.14.0.
- SymPy: 1.14.0; Python: 3.12.14.
- Solver process budget: 30 seconds; checker process budget: 20 seconds.
- Fresh processes, one job per engine, one repetition. Engine runs may overlap.

This is a coverage pilot, not a hardware-controlled timing experiment. Process
startup is included in the wall budget. The adapters report integration-entry
time separately. The checker is SymPy for both engines, so the SymPy comparison
is not independently verified by another CAS.

## Build and run

Build CE from the recorded clean checkout using its installed esbuild:

```sh
node node_modules/esbuild/bin/esbuild src/compute-engine/index.ts --bundle --platform=node --format=esm --outfile=/path/to/integral-benchmark/.cache/ce-current.mjs
```

The initial local build used esbuild 0.28.2. The run metadata records the bundle
hash, source revision, and dirty state. Bundle hashes may change with bundler or
dependency versions even when the mathematical behavior is unchanged.

From the benchmark checkout:

```sh
python -m integral_benchmark.cli seed
python -m integral_benchmark.cli inventory --upstream /path/to/pinned/upstream --output reports/inventory
python -m integral_benchmark.cli run --engine ce --ce-root /path/to/pinned/ce --ce-module .cache/ce-current.mjs --timeout 30 --verify-timeout 20 --jobs 1 --output reports/release-ce
python -m integral_benchmark.cli run --engine sympy --timeout 30 --verify-timeout 20 --jobs 1 --output reports/pilot-sympy
python -m integral_benchmark.cli recheck --input-run reports/release-ce --output reports/release-ce-checked --id pilot:sinc-half --id pilot:pv-cos-cubic --timeout 20
python -m integral_benchmark.cli report --inventory reports/inventory/inventory.json --run reports/release-ce-checked --run reports/pilot-sympy --output reports
```

Earlier development runs with short timeouts and changing adapter packaging are
excluded from the public baseline. Published runs retain every selected case,
including failures and inconclusive verification. Repeating a run may change
timeout outcomes on a different machine; compare solver outputs as well as counts.

The recheck records the addition of real/imaginary projections to the verifier's
expression vocabulary. It preserves all solver answers and timing data, retains
the previous verification evidence, and only rechecks the two affected cases.
With the current verifier those cases can also be checked directly in a fresh run.
