"""Render the measured baseline report from retained result JSON."""
import json,pathlib
R=pathlib.Path(__file__).resolve().parents[1]
p=json.load(open(R/'reports/physical.json'));m=json.load(open(R/'reports/physical-evidence/metrics.json'));t=p['timing'];w=p['power'];f=p['timing_sweep']
rows=[('Synthesized cell area',f"{p['synthesis_area_um2']:,.2f} µm²"),('Routed non-fill cell area',f"{p['area_um2']:,} µm²"),('Core area',f"{p['core_area_um2']:,} µm²"),('Die area',f"{p['die_area_um2']:,} µm²"),('Core utilization',f"{100*p['utilization']:.4f}%"),('Requested clock','50 ns / 20 MHz'),('Worst setup WNS / TNS',f"{t['timing__setup__ws']:.6f} / {t['timing__setup__tns']:.6f} ns"),('Worst hold WNS / TNS',f"{t['timing__hold__ws']:.6f} / {t['timing__hold__tns']:.6f} ns"),('Fixed-layout STA setup limit',f"{f['sta_limit_mhz']:.6f} MHz; period {f['pass_period_ns']:.6f} ns"),('Slew / capacitance violations',f"{m['design__max_slew_violation__count']} / {m['design__max_cap_violation__count']}"),('Antenna-violating nets / pins','56 / 69'),('Router / Magic DRC errors','0 / 0'),('Netgen LVS errors','0; circuits match uniquely'),('KLayout DRC / layout XOR','Blocked by executable-path lookup error; no pass claimed'),('Power estimate, total',f"{w['power_mw']['total']:.6f} mW at 5 MHz"),('Internal / switching / leakage power',f"{w['power_mw']['internal']:.6f} / {w['power_mw']['switching']:.6f} / {w['power_mw']['leakage']:.9f} mW"),('Estimated energy per workload block',f"{w['estimated_energy_pj_per_block']:.3f} pJ"),('Power annotation count',f"{w['annotated_pin_activities']:,} / {w['sta_pin_count']:,} STA pins ({w['annotation_count_ratio_pct']:.4f}%)"),('Checked gate-level workload','200 / 200 blocks matched'),('Workload duration',f"{w['activity_window_ns']:,.0f} ns"),('Observed workload throughput',f"{w['achieved_million_blocks_per_second']:.6f} million blocks/s"),('Peak throughput at 5 MHz','1.25 million blocks/s; 40 million products/s; 80 MOPS using 2 ops/MAC')]
text='# SKY130 measurement report\n\nMeasured configuration: **one 8-lane, four-stage PE**, five runtime element formats, FP32/BF16 output, 70-bit accumulation. **This is not a 4x4-array PPA result. The implementation is not signoff-clean.**\n\n'
text+='| Metric | Observed result |\n|---|---|\n'+'\n'.join(f'| {a} | {b} |' for a,b in rows)+'\n\n'
text+='## Routed timing by corner\n\nAll values are ns at the requested 50 ns clock. RC min/nom/max are crossed with TT 25 C/1.8 V, SS 100 C/1.6 V and FF −40 C/1.95 V.\n\n| Corner | Setup WNS | Setup TNS | Hold WNS |\n|---|---:|---:|---:|\n'
for c in f['corners']:
 text+=f"| {c} | {t['timing__setup__ws__corner:'+c]:.6f} | {t['timing__setup__tns__corner:'+c]:.6f} | {t['timing__hold__ws__corner:'+c]:.6f} |\n"
text+='''
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
GitHub publication remains incomplete.
'''
(R/'docs/physical-results.md').write_text(text)
