"""Render only observed metrics; absent checks stay explicitly unmeasured."""
import json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=json.loads((ROOT/'reports/physical.json').read_text())
t=p.get('timing',{});d=p.get('drc_lvs',{});e=p.get('electrical',{});power=p.get('power') or {};sweep=p.get('timing_sweep') or {}
def number(value,unit=''):
    return 'Not measured' if value is None else f'{value:,.6f}{unit}'
rows=[('Requested clock',number(p.get('requested_clock_ns'),' ns')),
      ('Synthesis cell area',number(p.get('synthesis_area_um2'),' µm²')),
      ('Routed cell area',number(p.get('area_um2'),' µm²')),
      ('Worst setup / hold slack',number(t.get('timing__setup__ws'),' ns')+' / '+number(t.get('timing__hold__ws'),' ns')),
      ('Setup TNS',number(t.get('timing__setup__tns'),' ns')),
      ('Slew / capacitance violations',str(e.get('design__max_slew_violation__count','Not measured'))+' / '+str(e.get('design__max_cap_violation__count','Not measured'))),
      ('Antenna nets / pins',str(d.get('antenna__violating__nets','Not measured'))+' / '+str(d.get('antenna__violating__pins','Not measured')))]
for name,key in [('Router DRC','route__drc_errors'),('Magic DRC','magic__drc_error__count'),('KLayout DRC','klayout__drc_error__count'),('Layout XOR','design__xor_difference__count'),('LVS','design__lvs_error__count')]:
    rows.append((name,str(d.get(key,'No completed result'))))
rows.extend([('Flow exit code',str(p.get('flow_exit_code','Not recorded'))),
             ('Fixed-layout STA setup limit',number(sweep.get('sta_limit_mhz'),' MHz')),
             ('Power estimate at 5 MHz',number(power.get('power_mw',{}).get('total'),' mW')),
             ('Checked gate blocks',str(power.get('blocks_checked','Not measured'))),
             ('Activity annotation',number(power.get('annotation_count_ratio_pct'),' %'))])
text='# SKY130 candidate measurement report\n\n'
text+=p.get('configuration','Unspecified implementation')+'. Five formats, 70-bit accumulation, FP32/BF16. This is not an array PPA result. **No completed signoff is claimed.** `make check-signoff` evaluates all retained evidence and fails on missing, stale or failing checks.\n\n'
text+=f"Generated measurement: {p.get('generated_utc','unknown')}. Last completed stage: `{p.get('last_completed_stage','unknown')}`.\n\n"
text+='| Metric | Observed result |\n|---|---|\n'+'\n'.join(f'| {k} | {v} |' for k,v in rows)+'\n\n'
text+='## Extracted timing corners\n\n| Corner | Setup slack (ns) | Hold slack (ns) |\n|---|---:|---:|\n'
for corner in sorted(k.split(':',1)[1] for k in t if k.startswith('timing__setup__ws__corner:')):
    text+=f"| {corner} | {number(t['timing__setup__ws__corner:'+corner])} | {number(t.get('timing__hold__ws__corner:'+corner))} |\n"
text+='''
## Scope and evidence

The 50 ns target remains unchanged. Retained SDC budgets, three RC corners and
TT/SS/FF cell corners define timing conditions; inspect the resolved configuration
under `reports/physical-evidence/`. Power is a TT/25 C/1.8 V OpenSTA estimate
using checked, zero-delay gate simulation at 5 MHz. Delay-induced glitches and
supply-network effects are excluded. Unannotated pins use tool defaults.
A clock-period sweep is a setup limit for the fixed layout, not qualified Fmax.

`reports/physical.json` records flow exit status, source hashes, netlist hash,
electrical results and DRC/LVS results. Missing metrics are never counted as zero.
`reports/signoff.json` records the independent acceptance result. Native UVM,
code/toggle coverage and full independent arithmetic proof are separate gates.
The converter rewrite proof compares all converter inputs to the frozen baseline;
it does not constitute full PE arithmetic equivalence against an independent spec.

The previously published measurements are preserved in
[physical-baseline.md](physical-baseline.md) and `reports/physical-baseline.json`.
Their routed artifacts remain in release `v0.1.1-measured`; they do not describe
the optimized candidate RTL. The original PDF write-ups also describe the earlier
milestone. See [signoff-closure.md](signoff-closure.md) for current closure work.
'''
(ROOT/'docs/physical-results.md').write_text(text)
