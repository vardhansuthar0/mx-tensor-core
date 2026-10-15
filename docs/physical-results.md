# SKY130 closure candidate

The current physical candidate is one eight-lane, five-stage PE at an unchanged
50 ns / 20 MHz target. Its routed signoff campaign is in progress. No completed
signoff or candidate PPA numbers are claimed by this interim document.

The published four-stage measurements are preserved in
[physical-baseline.md](physical-baseline.md) and `reports/physical-baseline.json`.
They do not describe the retimed five-stage candidate.

The final report is generated from `reports/physical.json` after collection.
`reports/signoff.json` and `make check-signoff` determine acceptance; absent,
stale, failed or blocked checks remain failures. See
[signoff-closure.md](signoff-closure.md) for implementation and verification work.
