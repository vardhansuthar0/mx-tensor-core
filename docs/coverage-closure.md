# Reachable PE coverage closure

The audit passes for PE/CSA line, branch, expression and toggle counters in all nine configurations. Raw counters are retained. This scope does not include array/APB code coverage or four-state X propagation.

| Lanes | Stages | Raw toggle | Unreachable toggle counters | Reachable counters |
|---:|---:|---:|---:|---|
| 8 | 3 | 99.676% | 26 | all hit |
| 8 | 4 | 99.676% | 26 | all hit |
| 8 | 5 | 99.676% | 26 | all hit |
| 16 | 3 | 99.596% | 50 | all hit |
| 16 | 4 | 99.596% | 50 | all hit |
| 16 | 5 | 99.596% | 50 | all hit |
| 32 | 3 | 98.725% | 242 | all hit |
| 32 | 4 | 98.731% | 241 | all hit |
| 32 | 5 | 98.731% | 241 | all hit |

Constant-state induction and phase/flag induction prove the exclusions; inverted properties must produce counterexamples. Elaboration constants account for the fixed-parameter assertion outcomes. Every excluded point is listed in the generated `reports/coverage-closure.json`. Unknown, failed or stale points block the gate.

Run `make reproduce` with native Yosys available. The verification workflow uploads full reports, generated harnesses and logs as its `verification-evidence` artifact. See `reports/reachable-coverage-summary.json` for the local proof and raw-report hashes.

This coverage result does not complete full PE arithmetic equivalence or physical signoff.
