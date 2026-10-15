# MX block-dot PE: implementation contract v0.1

## 1. Scope and numerical contract

This project is built only from public specifications (the OCP Microscaling
Formats spec and standard IEEE-754 behavior), so it shows the same class of
problem without claiming to replicate any real product. NVIDIA's internal
tensor-core designs are proprietary.

Primary source: OCP Microscaling Formats v1.0, September 2023, sections 5.2-5.4
and 6.1: https://www.opencompute.org/documents/ocp-microscaling-formats-mx-v1-0-spec-final-pdf
The table below was checked against Tables 1, 2, 4, 5 and 7.

| ID | Element | S/E/M | Bias | Maximum | Minimum subnormal | Specials |
|---|---|---|---|---|---|---|
| 0 | E4M3 | 1/4/3 | 7 | 448 | 2^-9 | +/-0, NaN at 0x7f/0xff |
| 1 | E5M2 | 1/5/2 | 15 | 57344 | 2^-16 | +/-0, +/-Inf, NaN |
| 2 | E3M2 | 1/3/2 | 3 | 28 | 2^-4 | +/-0 |
| 3 | E2M3 | 1/2/3 | 1 | 7.5 | 2^-3 | +/-0 |
| 4 | E2M1 | 1/2/1 | 1 | 6 | 2^-1 | +/-0 |

All five support subnormals. E8M0 scales 0x00..0xfe represent 2^(code-127);
0xff is NaN; there is no zero scale. Each block contains 32 elements,
independent of lane count. A and B use the same selected element format.
Upper padding bits of FP6/FP4 input bytes are ignored.

Finite decoding is integer significand times a power of two. Products and
the 32-term reduction are exact in EXACT mode; scale is applied only as an
exponent offset. No intermediate FP32 conversion occurs. The implementation
extends mathematical finite-element semantics even when a scaled individual
element lies outside FP32 range; only the final result overflows/underflows.
This is a project choice in an implementation-defined region of the MX spec.

Let q be the smallest positive element and M the maximum finite magnitude.
The exact signed accumulator needs W = 1 + bit_length(32*(M/q)^2), including
the sign. Its binary-point unit is q^2.

| Format | q^2 | Maximum integer sum | Minimum signed W |
|---|---|---|---|
| E4M3 | 2^-18 | 32*(448*512)^2 | 42 |
| E5M2 | 2^-32 | 32*(57344*65536)^2 | 70 |
| E3M2 | 2^-8 | 32*(28*16)^2 | 24 |
| E2M3 | 2^-6 | 32*(7.5*8)^2 | 18 |
| E2M1 | 2^-2 | 32*(6*2)^2 | 14 |

A runtime-selectable implementation must provision the worst case: a common
70-bit accumulator with unit 2^-32. Runtime format changes cannot remove
physical adder bits. A later fixed-format synthesis variant can use the
smaller widths above.

TRUNC(n), n=0..31, discards n low bits of each product on its format's q^2
grid, toward zero, before summation. It never arithmetic-right-shifts a
negative product to perform truncation. A separate approximation flag records
any discarded nonzero bit. Runtime TRUNC is an accuracy experiment; it does
not promise area savings without static specialization.

Output is FP32 or BF16, round-to-nearest, ties-to-even, directly from the wide
sum (no FP32-to-BF16 double rounding). BF16 occupies bits 15:0 of the 32-bit
output; bits 31:16 are zero. Gradual underflow is preserved. Tininess is
detected after rounding. Flags [4:0] are {approx, invalid, overflow,
underflow, inexact}. Inexact refers to final conversion of the accumulated
value; approx is separate. NaN inputs/scales, 0*Inf, opposite signed infinity
products, or reserved format IDs produce canonical quiet NaN and invalid.
All input NaNs are treated alike; no signaling/quiet distinction is claimed.
Infinity propagation alone does not raise overflow. Exact zero is +0,
including all-negative-zero inputs; a nonzero negative value rounded to zero
retains its sign. These zero and invalid policies are explicit project choices.

## 2. Streaming architecture

The baseline is a four-stage, synchronous-reset, single-clock PE. LANES is
8, 16 or 32. Each accepted beat supplies LANES bytes of A and B. Element i is
in bits 8*i +: 8. Beats are ordered; block boundaries are implicit every
32/LANES accepted beats. No interleaving between blocks is supported.
Format, output format, truncation count and scales are captured on the first
accepted beat; later beat sidebands are ignored. Reset aborts partial blocks
and all in-flight results. No result from before reset may retire afterward.

1. Decode: capture signs, 4-bit significands, signed exponents and special
   classifications. Metadata includes end-of-block and captured controls.
2. Multiply: one at-most-4x4 significand multiplier per lane, exponent sum,
   and product special classification. Finite results are aligned to 2^-32
   and optionally truncated on their native product grid.
3. Reduce/accumulate: a combinational carry-save tree reduces lane products,
   then a carry-propagate add incorporates earlier beats of this block.
   NaN and positive/negative infinity state accumulates separately.
4. Normalize/round: priority leading-one search, guard/sticky tie handling,
   exponent range handling, packing and per-result flags.

Global clock enable is !out_valid || out_ready. All pipeline state and the
input beat counter freeze during an output stall. in_ready is this enable
qualified by !reset. This intentionally simple backpressure scheme has a
combinational output-ready to input-ready path and does not accept new work
behind a stalled output. Payload and valid remain stable until accepted.
For LANES=32, initiation interval is one cycle when unstalled. For LANES=16/8,
it is 2/4 cycles per block. A first beat accepted at edge t produces the
registered output after edge t+(32/LANES-1)+3 in the absence of stalls.

PIPE_STAGES=3 bypasses the decode register, combining decode and multiply.
PIPE_STAGES=5 adds a register between completed sum and conversion. This
fifth stage registers magnitude and leading index before conversion rounding; routed timing still determines closure.
Its utility must be judged by measurement. Pipeline depth is elaboration-time.

## 3. Integration and sign-off

The array broadcasts each A row beat and B column beat to M*N PEs with a
shared block configuration and per-row/per-column scales. All outputs retire
atomically. It computes a K=32 matrix tile; arbitrary-K accumulation requires
a separately specified output accumulator. A result buffer provides one tile
of storage through the PE output registers. Do not describe that as an
arbitrary-K matrix MAC or a systolic architecture.

An APB configuration wrapper should snapshot the active register settings on
each PE's first accepted beat; write-one-to-clear sticky flags OR in new
events on the same edge so events are never lost. Performance counts retired
blocks, not input beats. Reserved controls must be rejected. Clock domains,
DMA and external memory are out of scope for the first implementation.

Sign-off gates: independent element cross-check, integer-reference numerical
regression, scoreboard transaction checks under stalls/reset, named functional
coverage bins with impossible crosses explicitly excluded, RTL mutation
campaign that requires a passing baseline and numerical/temporal assertion
failures for kills, separately bounded/unbounded formal results, and physical
reports with tool versions, PDK revision, corner, clock, parasitics, stimulus
and activity source. Unknown or unrun is never a passing result. Completion
status and deferred features are recorded in README and reports/status.json.

## Converter closure revision

The five-stage configuration now registers the 70-bit magnitude and seven-bit
leading index after the completed block sum, rather than copying the entire
sum into an otherwise redundant register stage. Sign, scale, output mode and
exception metadata remain aligned on the same global advance enable. Its
five-cycle accepted-beat latency and four-cycle initiation interval at eight
lanes are unchanged. Three- and four-stage configurations use the same
normalization network without the additional normalization registers.

Magnitude uses a preserved parallel-prefix OR network for two's-complement
negation; leading-index search has logarithmic depth; sticky bits use a parallel
mask reduction. `make converter-formal` proves the combinational conversion
against both the frozen baseline and an independent quotient/remainder RNE
specification. The separate four-/five-stage induction jobs cover reset and
stalled-output preservation, not full numerical pipeline correctness.
