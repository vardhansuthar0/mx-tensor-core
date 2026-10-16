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
branch/toggle coverage, or complete verification. `reports/code-coverage.json` now retains raw instrumented line/branch/expression/toggle counts and every uncovered counter across nine PE configurations. These counters have no exclusions or waivers; measurement does not imply closure. Functional coverage cannot prove correctness.

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

## Closure additions

`make converter-formal` proves the current converter (including the preserved
parallel-prefix magnitude network) equivalent to the converter frozen at
commit 835e63e for all 70-bit sums, 10-bit scales, output formats and special
flags. This is a rewrite-equivalence proof, not an independent numerical spec.

`make native-uvm` fetches Accellera UVM 2020.3.1 at commit
78c06547a2a0a29b3dc9dcafae62b75b2ff61544. A native SV sequence, sequencer,
driver, monitor and scoreboard check generated integer-model vectors through
the actual ready/valid interface of an 8-lane PE (five stages by default; `--stages` selects 3/4/5). LFSR backpressure
and a watchdog check stalls and draining. DPI/backdoor facilities are disabled;
UVM emits two associated capability warnings. This test uses initial reset;
the pyuvm campaign retains occupied-pipeline and partial-block reset testing.

The directed suite now includes infinity times infinity, RNE exponent carry,
and rounding a subnormal up to minimum normal. `make signoff-tests` tests that
the acceptance validator rejects known false-positive situations. Acceptance
requires original 50 ns timing across all nine extracted corners, zero
slew/capacitance/antenna/DRC/LVS/XOR violations, checked gate simulation on the
same netlist, current source hashes and completed verification gates. Missing,
non-finite, stale or failed results block acceptance. Full arithmetic formal
proof and coverage closure remain work items; no report field substitutes for
those proofs or measurements.

The converter additionally passes a combinational SAT comparison against the independently written `formal/converter_spec.svh`, which chooses an output quantum, divides exactly, and compares integer remainders to half a quantum. See `reports/converter-specification.json`. Full sequential numerical refinement remains separate.

The direct slang-based protocol harness now exposes symbolic values as actual
module input ports. Internal `anyseq` attributes were not sufficient with this
frontend: the netlist contained X constants instead of free inputs. Fresh
induction proofs and inverted-property counterexample controls replace those
old direct-Yosys results. Converter proofs already used explicit input ports.
The optional bounded numerical harness also uses explicit ports and verifies
that the frontend retains them before invoking the native backend.
