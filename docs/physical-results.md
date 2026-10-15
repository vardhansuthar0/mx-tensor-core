# SKY130 closure candidate — timing met, signoff blocked

The candidate is one **8-lane, 5-stage PE**, targeting **50 ns / 20 MHz**. The published baseline used four stages. This is not an array PPA result.

| Latest observed routed result | Value |
|---|---:|
| Worst setup slack, nine extracted corners | +3.229815 ns |
| Worst hold slack, nine extracted corners | +0.207146 ns |
| Slew violations | 2,339 |
| Capacitance violations | 9 |
| Antenna-violating nets / pins | 22 / 22 |
| Router DRC errors | 0 |
| Candidate Magic/KLayout DRC, XOR, LVS | Final evidence not recovered |

All nine reported setup slacks are positive at the unchanged target. **Electrical and antenna signoff remain failed.** The five-stage normalization split closes the observed timing failure; the repair settings do not close electrical/antenna violations.

These metrics were read from `physical/runs/p5-final/61-openroad-stapostpnr/state_out.json` before the execution environment disconnected. `reports/physical.json` preserves the observed values and labels them as a partial recovery. It is not a raw report archive or completed signoff evaluation. No candidate power, area, final LVS or independent DRC/XOR pass is inferred.

The published four-stage metrics and raw views remain historical evidence: [physical-baseline.md](physical-baseline.md), `reports/physical-baseline.json`, and release `v0.1.1-measured`.

Full sequential arithmetic refinement and raw coverage closure also remain open. `make check-signoff` must reject the partial evidence. See [signoff-closure.md](signoff-closure.md) and [PR #1](https://github.com/vardhansuthar0/mx-tensor-core/pull/1).
