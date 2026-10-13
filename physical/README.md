# SKY130 measured baseline

The measured instance is **one 8-lane, four-stage PE**, with all five formats,
FP32/BF16 output, and the 70-bit exact/runtime-truncating datapath. These are
not measurements of the 4x4 array. See `reports/physical.json` for the current
machine-readable result and `docs/physical-results.md` for the measurement report.

The design was synthesized, placed, clocked, routed, extracted, and analyzed
using OpenLane 2.3.10, OpenROAD and SKY130A/sky130_fd_sc_hd. The requested clock
was 50 ns. The implementation has known setup, slew, capacitance and antenna
violations. **It is not signoff-clean or tapeout-ready.**

## Reproduction

Use the pinned OpenLane tool environment (including Icarus Verilog/OpenSTA):

```sh
nix develop github:chipfoundry/openlane2/2.3.10
# Install yowasp-yosys in an accessible Python environment for read_slang.
# Enable the PDK revision recorded below with volare, and export PDK_ROOT.
make physical
```

PDK revision: `0fe599b2afb6708d281543108caf8310912f54af`.
The Python package versions are in `requirements-physical.txt`; they do not
install the native EDA executables. After tools/PDK setup, `make physical` runs
the flow, checked gate simulation, power and fixed-layout STA sweep. Any failed
flow checker retains a failing exit status. A flow stopped by a tool error can
be resumed with `scripts/physical.py --tag measured --from-step <step-id>`;
review the retained earlier error before making any signoff claim.

To re-analyze the supplied routed netlist and three extracted SPEFs without
repeating placement and routing:

```sh
make analyze-physical
```

`physical/results/analysis-state.json` contains portable paths. GDS, DEF,
netlist, SDC and SPEFs are supplied alongside it in the full release package.
Download that package before running this analysis target. Full run directories are
excluded from the release archive; timing/checker reports are copied to
`reports/physical-evidence/`. Raw tool logs retain original run paths.

On this hosted environment, native cached Nix binaries were used. Its `/proc`
PID namespace is incompatible with OpenLane's optional psutil resource
tracker; `MX_DISABLE_PROCESS_STATS=1` uses `scripts/openlane_host.py` to disable
CPU/RSS telemetry only. Design checkers and subprocess exit-status checks stay
active. KLayout's executable-path lookup also encountered a host error;
its failed checks are not treated as passes.

## Measurement definitions

- Cell area is OpenROAD's non-fill standard-cell area, including physical tap
  and antenna cells. Die/core area and utilization are reported separately.
- Timing includes three RC corners crossed with TT/SS/FF cell corners, routed
  parasitics, 5% timing derate, 0.25 ns clock uncertainty, 10 ns I/O delays and
  0.033442 pF output loads from the resolved SDC.
- The STA frequency limit is a 22-step clock-period bisection of this **fixed
  routed design**, keeping I/O budgets fixed. It is a setup limit, not a
  signoff-qualified Fmax, silicon measurement or PnR optimization sweep.
- Power uses nominal RC, TT/25 C/1.8 V, a 5 MHz clock, and zero-delay Icarus
  simulation of the final gate netlist. 200 deterministic blocks, five formats,
  both output types and truncation settings 0/2/7/15 are scoreboard checked.
  Uniform finite element codes and scale codes 120..134 are a synthetic workload,
  not an AI model workload. Idle intervals are included.
- Power is an OpenSTA estimate. Delay-induced glitches, unmodeled physical-cell
  leakage and supply-network effects are excluded. Unannotated pins use tool
  defaults. Annotation counts and workload duration accompany the result.
- Energy per block is estimated average power times waveform duration divided
  by checked blocks. Peak throughput uses one block per four accepted cycles;
  reported workload throughput includes idle cycles.

References: [OpenLane](https://openlane2.readthedocs.io/),
[OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD),
[OpenSTA](https://github.com/The-OpenROAD-Project/OpenSTA).
