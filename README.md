# MX tensor datapath - verification and SKY130 measurements

A SystemVerilog MX block-dot PE and 1x1/2x2/4x4 broadcast array, with a Python
integer reference, pyuvm/cocotb verification, assertions, formal properties and
manual RTL mutation testing. **K is 32. One PE has routed SKY130 measurements;
physical signoff remains incomplete.** See `reports/status.json` for measured
verification results, tool versions and limitations.

This project is built only from public specifications (the OCP Microscaling
Formats spec and standard IEEE-754 behavior), so it shows the same class of
problem without claiming to replicate any real product. NVIDIA's internal
tensor-core designs are proprietary.

## Reproduce

On Linux x86-64 with Python 3.12, a C++ compiler, Make and native Yosys:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
# Ubuntu/Debian: sudo apt-get install yosys
make reproduce
```

After setup, **`make reproduce`** runs model checks, warning-fatal lint,
all nine PE configurations, three array sizes, structural/protocol/converter formal jobs and the nine-
mutant campaign, exhaustive product-pair enumeration, native SV UVM and instrumented RTL coverage with proven-unreachable-point auditing. It stops on failures and writes evidence under `reports/`.
The pinned Verilator wheel reports a development engine version; both wheel
version and raw simulator banners are retained. A local Make override avoids
its precompiled-header include issue. Yosys uses the pinned WebAssembly build
with its slang SystemVerilog frontend. Coverage induction uses a native SAT
backend (`yosys` on PATH or `YOSYS_NATIVE`); that backend reads lowered JSON
and does not need the slang plugin.

Individual targets: `make model lint sim array formal mutation converter-formal native-uvm code-coverage`.
`make physical` requires an OpenLane 2 tool environment and SKY130 PDK.
`make arithmetic-composed` runs the complete compositional PE arithmetic campaign.
`make signoff` includes that campaign and physical execution, and fails when either is unavailable;
its final validator rejects missing, stale or failing timing, electrical, antenna, DRC/LVS/XOR and verification evidence. `make check-signoff` evaluates retained reports without rerunning EDA tools.

## Implemented contract

- E4M3, E5M2, E3M2, E2M3 and E2M1; same format for A/B, runtime selectable.
- 32-element blocks with E8M0 scales; 8/16/32 lanes take 4/2/1 accepted beats.
- Exact 70-bit signed accumulation, or runtime TRUNC(n), n=0..31, on each
  format's native product grid. Truncation is toward zero before summation.
- FP32/BF16 direct round-to-nearest-even, gradual underflow, canonical NaNs,
  infinity handling and per-result exception/approximation flags.
- 3/4/5 pipeline stages, synchronous reset and ready/valid backpressure.
- MxN broadcast tile: C[r,c] = dot(A[r,0:32], B[0:32,c]). Output PE registers
  buffer one completed tile; no arbitrary-K running tile accumulator exists.
- APB configuration, write-one-to-clear sticky flags and retired-tile counter.

Read `docs/microarchitecture.md` before the RTL. The specification was written
before implementation; it derives the required signed accumulator widths as
42/70/24/18/14 bits. Runtime format selection provisions the worst-case width.
The fifth stage registers the completed magnitude and leading-bit index, splitting normalization from rounding. Three- and four-stage configurations retain combinational normalization.

## Interfaces and software-visible registers

The PE uses low-byte-first packed lanes: lane i is bits `8*i +: 8`. FP4/FP6
occupy low bits of each byte. There is no TLAST; accepted-beat count defines a
block. Control and scales are latched on its first accepted beat. Reset aborts
partial and in-flight work. Exact cancellation and all-zero sums return +0.
BF16 results occupy output bits 15:0, with zero upper bits.

Array A is row-major packed beats, B is column-major packed beats. Scale A
has one byte per row, scale B one per column. Output index is r*N+c. All tile
outputs retire atomically; one stalled consumer stops every PE.

| APB offset | Access | Meaning |
|---|---|---|
| 0x00 | RW | bits 2:0 format ID; bit 3 BF16; bits 8:4 truncation count; upper bits zero |
| 0x04 | RW1C | bits 4:0 sticky {approx, invalid, overflow, underflow, inexact} |
| 0x08 | RO | retired tiles, 32-bit wrapping counter |
| 0x0c | RO | {M[7:0], N[7:0], LANES[7:0], PIPE_STAGES[7:0]} |

Format IDs are 0=E4M3, 1=E5M2, 2=E3M2, 3=E2M3, 4=E2M1. RNE is the only
rounding mode. Invalid addresses, format IDs, reserved write bits and writes
to RO registers produce PSLVERR and no state change. APB never inserts wait
states. A register write concurrent with first-beat acceptance affects the
next block; that beat sees the old register value. New exception events win
against simultaneous W1C. Sticky flags count retired results, not aborted work.

## Evidence and limits

`docs/verification-plan.md` defines the 160 contract bins and seven rounding
classes, sampling rules, seeds, formal scope, mutation validity rules and
remaining verification work. Coverage is sampled from observed, checked
transactions. The campaign must kill all named planted defects, but does not
claim to detect all possible bugs. Native SystemVerilog UVM now checks the 8-lane/five-stage PE using pinned Accellera UVM 2020.3.1. Instrumented line/branch/expression/toggle counters are measured across all nine PE configurations, with uncovered points retained. The converter rewrite is formally equivalent to baseline and to an independent integer-RNE specification for all converter inputs. **The full compositional PE arithmetic certificate passes all nine configurations**, including arbitrary bubbles, stalls and later resets after initial reset, all metadata, and all five formats plus reserved-format poison. It combines 27,262,976 exhaustive lane cases, full CSA structural induction, unbounded stream/register proofs and independent scalar-converter SAT proofs. See `reports/arithmetic-equivalence.json` and `docs/arithmetic-composition.md`. **Reachable PE/CSA code and toggle coverage is closed with individually proved unreachable points; raw counters are preserved.** Array/APB code/toggle coverage and four-state X analysis remain unmeasured. See `docs/coverage-closure.md` and `docs/signoff-closure.md`.

`physical/README.md` gives the physical handoff and reporting requirements.
The published baseline has routed area, timing and activity-based power estimates for one 8-lane/four-stage PE. Its measurements are preserved in `docs/physical-baseline.md`; the optimized candidate requires fresh physical evidence. See `docs/physical-results.md`. The baseline fails the 20 MHz slow-corner target and has electrical/antenna violations. The candidate keeps the 50 ns target, selects the existing five-stage PE with split conversion, alternates post-global-route electrical and antenna repairs, and uses tighter clock-tree load limits. **No signoff closure is claimed until all acceptance gates pass.**
The two-page PDF documents retain the earlier RTL milestone; the physical report
and machine-readable results supersede their physical-status statements.

## Repository map

| Path | Purpose |
|---|---|
| rtl/ | PE, recursive CSA reduction, APB array |
| model/ | Integer-only numerical reference |
| tb/ | Model checks, pyuvm agent/scoreboard, array/APB tests |
| formal/ | CSA and protocol harnesses, optional SBY handoff |
| scripts/ | Regressions, lint, mutation, formal, physical preflight |
| reports/ | Raw logs, JSON evidence, source hash manifest |
| docs/ | Micro-architecture, verification plan, write-up, resume bullets |
| physical/ | OpenLane configuration, routed artifacts and measurement methodology |

## Published repository

Public source: https://github.com/vardhansuthar0/mx-tensor-core

The `v0.1.1-measured` release contains the published four-stage routed views and raw reports. Candidate results are identified separately by configuration and source hashes.
The repository contains the RTL, model, verification, scripts, summaries and
key logs. GitHub Actions runs the verification suite on pushes; its result
must be checked separately from the local measurements.
