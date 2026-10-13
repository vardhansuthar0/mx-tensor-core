# Resume bullets - measured RTL milestone

- Implemented a SystemVerilog MX block-dot datapath supporting five FP8/FP6/FP4 formats, 8/16/32 lanes and 3/4/5 pipeline stages, with exact 70-bit accumulation, FP32/BF16 rounding and a 4x4 APB-controlled tile array.

- Built a pyuvm/cocotb verification environment checking 48,180 block outputs across nine configurations; closed 160/160 declared functional bins and 7/7 rounding classes per configuration, with 656 element encodings independently cross-checked.

- Detected 9/9 planted RTL defects and proved a 70-bit CSA identity plus unbounded reset/backpressure properties using Yosys SAT; automated regressions, formal checks and mutation testing behind one Make command.

Do not add SKY130 area, MHz, power, routed-layout, full-UVM or end-to-end arithmetic-formal claims until those milestones are complete.
