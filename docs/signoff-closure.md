# Signoff closure work

This branch is a closure candidate. A successful verification regression is
not a completed physical signoff. `make check-signoff` is the acceptance gate;
`reports/signoff.json` records its actual result and remaining failures.

## Implemented fixes

- The baseline slow path traversed a long shared OR-prefix chain in magnitude
  conversion. The RTL now preserves a parallel prefix, uses logarithmic
  leading-bit search and parallel sticky reduction.
- The existing five-stage option registers magnitude and leading index before
  rounding. Latency and initiation interval stay within the documented
  parameterized contract. The physical candidate selects eight lanes and five
  stages; the published baseline used four stages. The clock remains 50 ns.
- Converter SAT proofs cover every 70-bit sum, 10-bit scale, output mode and
  special-flag combination, against both the frozen baseline and an independent
  integer quotient/remainder RNE specification.
- The protocol harness uses explicit symbolic input ports. The slang frontend
  used in this project turned the earlier internal symbolic-attribute variables
  into undriven X values. Those earlier direct-Yosys protocol results must not
  be relied on. Fresh four-/five-stage induction proofs replace them. Deliberate
  wrong reset and converter properties must produce counterexamples; crashes,
  timeouts and compile failures never count as successful negative controls.
- Native SystemVerilog UVM uses pinned Accellera UVM 2020.3.1, real sequence/
  sequencer/driver/monitor/scoreboard components, model-generated vectors and
  deterministic backpressure. The current default is the eight-lane/five-stage
  PE; DPI/backdoor facilities are disabled. The pyuvm suite retains the broader
  parameter, reset, bubble, throughput and APB/array campaigns.
- Instrumented RTL line/branch/expression/toggle counts are retained per PE
  configuration, with every uncovered counter and no implicit waivers.
  New directed tests exercise infinity times infinity, exponent carry and
  subnormal-to-minimum-normal RNE promotion.
- Physical repair alternates electrical repair with four antenna-repair passes,
  accounting for added diode loading. Clock-tree load limits were tightened.
  These are optimization settings; only final routed checks establish closure.
- A narrow, opt-in KLayout host interposer translates only this process's
  `/proc/<pid>/exe` lookup to `/proc/self/exe`. KLayout batch execution, XOR and
  DRC were exercised after this fix. Python helper scripts use the OpenLane
  driver's interpreter to prevent a reproduced 3.11/3.12 standard-library
  mismatch. Emitted reports are flushed before downstream parsing.
- The collector retains flow exit status, input/netlist hashes, all timing
  corners, electrical violations and KLayout/XOR checks. The report generator
  renders observed metrics instead of historical hardcoded pass counts.
- A regression snapshots its sources before running and requires unchanged
  sources plus fresh result files before writing a passing summary. The
  validator tests exercise stale data, missing checks/corners, non-finite
  metrics, relaxed clock targets and false completion claims.

## Arithmetic and coverage closure

The full compositional PE arithmetic certificate passes all nine supported
lane/pipeline configurations. It covers every raw byte encoding, supported
format and reserved-format poison, all scale/truncation/output metadata, and
arbitrary bubbles, stalls and later resets after initial synchronous reset.
The claim uses two-state RTL semantics and is scoped to the PE.

The certificate connects the exhaustive independent lane contract, full CSA
structural induction, actual lane replication/register bindings, unbounded
stream/metadata/accumulation refinement, normalization/output capture, and
all-input independent integer-RNE scalar conversion. Source and report hashes
bind every component. All positive and deliberately wrong control obligations
must pass their respective proof/counterexample requirements. Six corrupted
evidence controls verify that the assembler rejects incomplete or stale claims.

Run `make arithmetic-composed`. See [arithmetic-composition.md](arithmetic-composition.md)
for the cut-point contracts and exact integer range argument, and
`reports/arithmetic-equivalence.json` for the actual certificate. The passing
[hosted campaign](https://github.com/vardhansuthar0/mx-tensor-core/actions/runs/38835214797)
retains an eight-JSON certificate artifact. This does not certify physical
checks, array/APB equivalence or four-state X behavior.

The optional bounded monolithic harness remains a separate experiment.
Its resource-limited attempts are not counted as passing evidence; the
certificate above uses compositional obligations instead.

Raw coverage retains parameter-constant branches and structural constant bits.
The reachable PE/CSA coverage audit passes all nine configurations using
unbounded constant-state induction, a separate phase/flag branch proof and
explicit elaboration constants. Every point is individually listed in
`reports/coverage-closure.json`; raw counts are unchanged. All proof campaigns
require deliberately wrong properties to produce actual counterexamples.
Array/APB code coverage and four-state X-propagation coverage have not been
established.

The resumed campaign checks 13,612 blocks per configuration and adds sparse
fixed-point powers, mixed carry populations and per-lane special events.
Five-stage raw toggle coverage is 99.676% at eight lanes, 99.596% at sixteen
lanes and 98.731% at thirty-two lanes. Line coverage is 100% in all nine
configurations. `make coverage-closure` proves and audits every remaining
PE/CSA counter; a failed or stale campaign never grants exclusions.

`make product-exhaustive` checks all 27,262,976 assignments to a one-lane
product cone extracted verbatim from the production RTL: both full input bytes,
five supported formats with poison on/off, three reserved formats with
required poison, and every truncation. The independent reference
uses fixed-point element magnitudes and wide integer multiplication. Signed
70-bit products and the four special/approximation flags match for every
assignment; an inverted production product bit is detected. This is one component of the full certificate, rather than a standalone
sequential PE proof. It also measures the maximum finite product and checks
that 32 such magnitudes fit in signed 70 bits.

## Physical evidence

The new candidate's results belong in `reports/physical.json` and
[physical-results.md](physical-results.md), with the final acceptance result in
`reports/signoff.json`. The original four-stage routed measurements remain in
`reports/physical-baseline.json` and [physical-baseline.md](physical-baseline.md).
They are historical evidence, not measurements of the retimed five-stage RTL.
All final routed timing, electrical, antenna, DRC, LVS and XOR checks remain
mandatory. Missing or blocked checks prevent a signoff claim.

Reproduction: `make reproduce`, `make physical` in the pinned native EDA/PDK
environment, then `make check-signoff`. `make signoff` runs the complete flow
and acceptance check. On the hosted PID-namespace environment, also set
`MX_DISABLE_PROCESS_STATS=1 MX_KLAYOUT_PROC_SELF_EXE=1`. The optional bounded
arithmetic target requires a native Yosys backend via `YOSYS_NATIVE` and may
need substantial memory; it is separate from the default CI campaign.

## Latest observed physical outcome

The latest completed local slow-corner repair experiment met the unchanged
50 ns target across all nine extracted corners: worst setup +3.340073201 ns
and worst hold +0.212931678 ns. Router, Magic and KLayout DRC, XOR and LVS
reported zero errors; routed gate simulation checked 200 blocks. It still had
98 slew, 4 capacitance and 16 antenna-net/pin violations.

Those observations precede the final clock-net and adjacent-diode ECO fixes.
They are not measurements of the fully repaired candidate. The local
execution environment disconnected during its reroute. A fresh pinned
[hosted physical run](https://github.com/vardhansuthar0/mx-tensor-core/actions/runs/38832427461)
is executing the complete flow with every final checker retained. PR #1 stays
draft until actual complete evidence satisfies the full signoff gate.
