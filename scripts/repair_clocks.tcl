# Explicit clock electrical repair; resizer normally avoids clock nets.
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
source $::env(SCRIPTS_DIR)/openroad/common/resizer.tcl
load_rsz_corners
read_current_odb
set_propagated_clock [all_clocks]
source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl

set changed 0
foreach inst [get_cells -hierarchical clkbuf_*] {
    set master [get_property $inst ref_name]
    if { $master == "sky130_fd_sc_hd__clkbuf_1" || $master == "sky130_fd_sc_hd__clkbuf_2" } {
        replace_cell $inst sky130_fd_sc_hd__clkbuf_4
        incr changed
    }
}
puts "Clock buffers strengthened: $changed"
estimate_parasitics -placement
repair_clock_nets -max_wire_length 100
source $::env(SCRIPTS_DIR)/openroad/common/dpl.tcl
source $::env(SCRIPTS_DIR)/openroad/common/grt.tcl
write_views
