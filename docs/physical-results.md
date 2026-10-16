# SKY130 candidate: physical signoff remains incomplete

The latest hosted physical attempt used one eight-lane, five-stage PE, a
70-bit accumulator and the unchanged 50 ns / 20 MHz target. It stopped after
the first detailed antenna ECO round, before final extraction and independent
checks. No physical signoff is claimed.

| Observation | Actual value |
| --- | --- |
| Source commit | 43394b2a94f57d1ec5f1c083dc0663125aab88e6 |
| Workflow run | [38832427461](https://github.com/vardhansuthar0/mx-tensor-core/actions/runs/38832427461) |
| Flow exit code | 2 |
| Last completed stage | 065-mx-ecocheckantennas |
| Checkpoint standard-cell area | 305,070 µm² |
| Checkpoint utilization | 22.7568% |
| Router DRC errors at the completed reroute | 0 |
| Antenna nets / pins | 23 / 23 |
| Final nine-corner timing and electrical checks | Not reached |
| Magic / KLayout DRC, LVS and XOR | Not reached |
| Routed gate simulation and power | Not reached |

The raw numeric partial report is `reports/physical.json`; the immutable
attempt copy is `reports/physical-attempt-38832427461.json`. The checkpoint
area and router result are not final signoff measurements.

The next closure attempt uses raw OpenROAD antenna records rather than the
rounded/wrapped presentation table, a wider legal adjacent-diode search and
retained final-error diagnostics. The complete signoff workflow replays
verification and arithmetic before the routed flow and then evaluates the
full source-bound acceptance gate. Every extracted timing/electrical corner,
antenna check, independent DRC, LVS, XOR and routed gate simulation must pass.

The earlier four-stage measurements remain historical in
[physical-baseline.md](physical-baseline.md). Earlier milestone statements
do not supersede this physical-status report. See
[signoff-closure.md](signoff-closure.md) for the completed arithmetic and
reachable PE/CSA coverage evidence and the separately labeled local physical
observations preceding this hosted attempt.
