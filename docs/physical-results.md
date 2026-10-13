# SKY130 measurement report

Measured configuration: **one 8-lane, four-stage PE**, five runtime element formats, FP32/BF16 output, 70-bit accumulation. **This is not a 4x4-array PPA result. The implementation is not signoff-clean.**

| Metric | Observed result |
|---|---|
| Synthesized cell area | 195,214.73 µm² |
| Routed non-fill cell area | 222,750 µm² |
| Core area | 1,340,570 µm² |
| Die area | 1,440,000 µm² |
| Core utilization | 16.6161% |
| Requested clock | 50 ns / 20 MHz |
| Worst setup WNS / TNS | -4.371589 / -132.846911 ns |
| Worst hold WNS / TNS | 0.108154 / 0.000000 ns |
| Fixed-layout STA setup limit | 18.391938 MHz; period 54.371649 ns |
| Slew / capacitance violations | 637 / 24 |
| Antenna-violating nets / pins | 56 / 69 |
| Router / Magic DRC errors | 0 / 0 |
| Netgen LVS errors | 0; circuits match uniquely |
| KLayout DRC / layout XOR | Blocked by executable-path lookup error; no pass claimed |
| Power estimate, total | 1.008295 mW at 5 MHz |
| Internal / switching / leakage power | 0.558623 / 0.449493 / 0.000178822 mW |
| Estimated energy per workload block | 910.490 pJ |
| Power annotation count | 82,517 / 84,427 STA pins (97.7377%) |
| Checked gate-level workload | 200 / 200 blocks matched |
| Workload duration | 180,600 ns |
| Observed workload throughput | 1.107420 million blocks/s |
| Peak throughput at 5 MHz | 1.25 million blocks/s; 40 million products/s; 80 MOPS using 2 ops/MAC |

## Routed timing by corner

All values are ns at the requested 50 ns clock. RC min/nom/max are crossed with TT 25 C/1.8 V, SS 100 C/1.6 V and FF −40 C/1.95 V.

| Corner | Setup WNS | Setup TNS | Hold WNS |
|---|---:|---:|---:|
| nom_tt_025C_1v80 | 22.546547 | 0.000000 | 0.330986 |
| nom_ss_100C_1v60 | -3.842807 | -115.318155 | 0.902471 |
| nom_ff_n40C_1v95 | 27.478584 | 0.000000 | 0.110253 |
| min_tt_025C_1v80 | 22.843672 | 0.000000 | 0.327945 |
| min_ss_100C_1v60 | -3.297263 | -97.297249 | 0.892975 |
| min_ff_n40C_1v95 | 27.597879 | 0.000000 | 0.108154 |
| max_tt_025C_1v80 | 22.253913 | 0.000000 | 0.333278 |
| max_ss_100C_1v60 | -4.371589 | -132.846911 | 0.910859 |
| max_ff_n40C_1v95 | 27.357230 | 0.000000 | 0.111806 |

## Interpretation and evidence

The STA sweep brackets the zero-setup-slack period to 0.000239 ns, retaining
the fixed layout, parasitics, I/O delays, derates and clock uncertainty. This
numerical precision does not imply silicon accuracy. 18.392 MHz is a **setup
limit**, not a signoff-qualified Fmax: slew, capacitance and antenna violations
remain. At 5 MHz, the nine-corner setup/hold slacks are +145.628/+0.108 ns.

Power uses TT/25 C/1.8 V and nominal routed parasitics. Its deterministic
synthetic workload uses uniformly sampled finite element codes, scales
120..134, five formats, both output formats, truncation 0/2/7/15 and idle gaps.
Gate-level results are checked against the integer golden model. Simulation
has zero cell delays: glitches are excluded. Unannotated pins use defaults;
physical cells without Liberty power models are excluded. Energy per block
includes idle time in the measured window. These are tool estimates, not
measurements from fabricated silicon.

LVS compares 23,274 devices and 23,228 nets on each side and reports a unique
match. Router DRC and Magic's full DRC deck report zero errors. KLayout DRC
and XOR failed before producing results because executable-path lookup in
`tlFileUtils.cc` is incompatible with this host's PID namespace. An alternate
installed KLayout binary produced the same error. This was not waived as a pass.

The original synthesis/placement run was resumed after a host resource-tracker
hang. Only optional CPU/RSS monitoring was disabled; design checkers remained
active. After KLayout XOR stopped the flow, Magic DRC and the independent
SPICE extraction/LVS stages were run from the same routed checkpoint.

Evidence: `reports/physical.json`, `reports/physical-evidence/`,
`reports/timing-sweep.log`, `reports/routed-power.log`,
`reports/gate-activity.json`, and `reports/physical-toolchain.json`.
Reproduction and full assumptions: `physical/README.md`.
Routed views and portable analysis inputs: `physical/results/`.

## Existing verification metrics (unchanged RTL)

- 48,180 PE blocks checked across nine lane/pipeline configurations.
- 160/160 declared contract bins plus 7/7 rounding bins per configuration.
- 9/9 named planted RTL defects detected; not a claim about all possible bugs.
- 90 array tiles / 630 PE results checked across 1x1, 2x2 and 4x4 arrays.
- 656 element encodings independently cross-checked; 44,000 rounding checks.
- Compressor equivalence and protocol/reset/backpressure formal properties pass.
- End-to-end numerical formal proof and measured RTL code coverage remain open.

Physical measurements cover one configuration; a lane/depth/array PPA sweep
has not been run. Runtime truncation keeps the same hardware width. Public
GitHub source is published at https://github.com/vardhansuthar0/mx-tensor-core.
