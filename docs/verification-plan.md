# Verification plan and claim boundaries

## Numerical reference

`model/mx.py` decodes integer significands and exponents. Its signed arbitrary-
precision sum is rounded once, directly to the destination. RTL uses a common
70-bit grid; the Python model uses the format-native grid. That difference
helps expose alignment errors. Exhaustive `ml_dtypes` comparison covers all
656 encodings; 40,000 independent casts and 4,000 Fraction midpoint checks
cross-check the rounder. These checks establish the model, not an exhaustive
RTL arithmetic proof. Input quantization from FP32 to MX is not implemented.

## Testbench organization

The pyuvm test builds an environment, agent and scoreboard. The agent owns a
cocotb clock BFM and executes deterministic directed/constrained-random block
sequences. A passive observation method samples actual DUT pins before each
clock edge, assembles only accepted beats, snapshots first-beat controls and
queues expected results. The scoreboard compares every retired data/flag pair
and detects unsolicited, duplicated, missing or early results. The generator
is a Python sequence generator, not a full native-UVM sequencer/driver port
implementation. No commercial simulator or native covergroup claim is made.

Checks cover stalls, bubbles, reset with occupied stages, partial-block reset,
first-beat configuration snapshots, FP4/FP6 padding bits, all input scale bytes,
NaN scales, specials, cancellation, overflow, underflow, and RNE midpoints.
A 64-block no-bubble test checks measured initiation interval. Random seed is
20261011; protocol random seed is 7331. The APB/array seed is 438.

## Functional coverage

160 explicit bins = 5 formats x 2 output formats x 2 accumulation settings
(EXACT and TRUNC(1)) x 8 scenarios: zero, all-min-subnormal, all-max-finite,
exact cancellation, both scales zero, both scales 254, NaN scale A, NaN scale B.
Scenarios are classified from accepted payload/control values, not a stimulus
tag. A bin is awarded only when its output retires and passes the scoreboard.
Seven additional bins classify exact/below-half/tie-even/tie-odd/above-half/
overflow/underflow inputs to final conversion. Runtime truncations 4/8/16/31
are also exercised by random stimulus, but are not crossed into the 160-bin
claim. Format-specific infinity/NaN cases are directed tests; impossible FP4/
FP6 special-element crosses are excluded by construction. A scale NaN is
possible for every format.

100% means these 167 declared bins, independently in each PE configuration.
It does not mean all possible inputs, all rounding/format/control crosses,
branch/toggle coverage, or complete verification. There is no code-coverage
percentage in this release. Functional coverage cannot prove correctness.

## Assertions and formal

RTL SVA checks output stability/valid persistence under backpressure, reset
flush, legal beat-counter range, and array lockstep. Verilator evaluates these
in all RTL regressions. Verilator is a two-state simulator; X-propagation and
four-state unknown checks are not established by these runs.

The formal harness uses unconstrained data/control inputs and requires reset
initially. Yosys SAT proves the 70-bit three-input CSA compressor identity
modulo 2^70. Yosys temporal induction proves PE output hold and reset/input-
ready properties for LANES=8/PIPE_STAGES=4. These are unbounded structural/
protocol properties; they do not prove the entire numerical datapath, arbitrary
array configurations, fairness or eventual progress. `formal/protocol.sby` is
an optional SymbiYosys handoff; the recorded proofs use direct Yosys SAT, not
an executed SymbiYosys run.

## Mutation campaign

The script first requires a passing baseline, then edits an isolated copy of
one RTL expression for each mutant. It reuses the same checker/reference.
A kill requires a scoreboard/protocol or RTL assertion failure after simulation
starts. Build errors, unsupported syntax, timeouts and tool crashes are invalid
experiments, never kills. Survivors fail the target. This release plants nine
named defects: backpressure, scale bias, subnormal exponent, E4M3 max encoding,
product sign, tie breaking, NaN scale handling, accumulation of prior beats,
and truncation enable. This is a small manual campaign, not exhaustive fault
coverage or Yosys mcy coverage. Logs and exact substitutions are included.

## Closure beyond this release

Add coverage of overflow rounding thresholds and tininess after rounding per
format, formal conservation/latency and bounded end-to-end FP4 equivalence,
four-state simulation, code/toggle coverage, longer/multiple random seeds,
cross-block matrix accumulation, and workload-driven physical power analysis.
None is implied complete by the first milestone's coverage or mutation score.
