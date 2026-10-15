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
  sources plus fresh result files before writing a passing summary. Fifteen
  validator tests exercise stale data, missing checks/corners, non-finite
  metrics, relaxed clock targets and false completion claims.

## Remaining proof and coverage work

Full sequential PE arithmetic refinement against an independent specification
is not complete. The optional `make arithmetic-bounded` harness uses explicit
symbolic input ports and captures a complete block at reset, with contiguous
valid beats and an always-ready output. Its deliberately inverted known-zero
control must fail. A passing named case covers only that format/configuration
and control trace; it never substitutes for arbitrary-stream arithmetic proof.
See `reports/arithmetic-bounded.json` for the exact attempted case. The fully
symbolic FP4 unroll exceeded the WebAssembly backend budget; the native SAT
attempt expanded to 11,439,943 variables and 33,454,884 clauses and was killed.
No numerical-equivalence pass is inferred from that attempt. An SMT attempt reached the final assertion but its completion was not recovered
after the execution environment disconnected. No SMT pass is claimed.

Raw coverage is measured, but remaining counters require reachable stimulus or
explicit, justified exclusions. Parameter-constant branches and structural
constant bits are retained in the raw report. Array/APB code coverage and
four-state X-propagation coverage have not been established.

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

## Latest recovered outcome

The five-stage candidate meets the 50 ns timing target across all nine extracted
corners (+3.229815 ns worst setup, +0.207146 ns worst hold), but has 2,339 slew,
9 capacitance and 22 antenna-net/pin violations. Router DRC reported zero errors.
The environment became offline during final independent checks and report
collection. PR #1 is a draft; the task is not complete and signoff is not claimed.
See `reports/physical.json` for explicitly labeled partial observations.
