`timescale 1ns/1ps
interface mx_if(input logic clk);
    logic rst=1, in_valid=0, in_ready, out_valid, out_ready=0;
    logic [63:0] in_a=0,in_b=0;
    logic [7:0] in_scale_a=127,in_scale_b=127;
    logic [2:0] in_fmt=0;
    logic in_bf16=0;
    logic [4:0] in_trunc=0,out_flags;
    logic [31:0] out_data;
endinterface
package mx_uvm_pkg;
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    class mx_item extends uvm_sequence_item;
        `uvm_object_utils(mx_item)
        bit [255:0] a,b;
        bit [7:0] sa,sb;
        bit [2:0] fmt;
        bit bf;
        bit [4:0] trunc,flags;
        bit [31:0] data;
        function new(string name="mx_item"); super.new(name); endfunction
    endclass
    class mx_sequence extends uvm_sequence #(mx_item);
        `uvm_object_utils(mx_sequence)
        int count;
        function new(string name="mx_sequence"); super.new(name); endfunction
        task body();
            int fd,n; string path;
            mx_item item;
            if(!$value$plusargs("vectors=%s",path)) `uvm_fatal("VECTORS","Missing vector file")
            fd=$fopen(path,"r");
            if(fd==0) `uvm_fatal("VECTORS","Cannot open vector file")
            while(!$feof(fd)) begin
                item=mx_item::type_id::create("item");
                n=$fscanf(fd,"%h %h %h %h %h %h %h %h %h\n",item.a,item.b,item.fmt,item.sa,item.sb,item.bf,item.trunc,item.data,item.flags);
                if(n==9) begin start_item(item); finish_item(item); count++; end
                else if(n>0) `uvm_fatal("VECTORS","Malformed vector")
            end
            $fclose(fd);
            if(count==0) `uvm_fatal("VECTORS","Empty vector file")
        endtask
    endclass
    class mx_scoreboard extends uvm_scoreboard;
        `uvm_component_utils(mx_scoreboard)
        uvm_tlm_analysis_fifo #(mx_item) expected;
        int checked;
        function new(string name,uvm_component parent); super.new(name,parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase); expected=new("expected",this);
        endfunction
        task check_result(bit [31:0] data,bit [4:0] flags);
            mx_item item;
            if(!expected.try_get(item)) `uvm_fatal("UNSOLICITED","Unexpected result")
            if(data!==item.data || flags!==item.flags)
                `uvm_fatal("MISMATCH",$sformatf("expected %h/%h got %h/%h",item.data,item.flags,data,flags))
            checked++;
        endtask
    endclass
    class mx_driver extends uvm_driver #(mx_item);
        `uvm_component_utils(mx_driver)
        virtual mx_if vif;
        uvm_analysis_port #(mx_item) expected;
        function new(string name,uvm_component parent); super.new(name,parent); expected=new("expected",this); endfunction
        task run_phase(uvm_phase phase);
            mx_item item;
            wait(!vif.rst);
            forever begin
                seq_item_port.get_next_item(item);
                for(int beat=0;beat<4;beat++) begin
                    @(negedge vif.clk);
                    vif.in_valid=1;
                    vif.in_a=item.a[beat*64+:64]; vif.in_b=item.b[beat*64+:64];
                    vif.in_fmt=item.fmt; vif.in_scale_a=item.sa; vif.in_scale_b=item.sb;
                    vif.in_bf16=item.bf; vif.in_trunc=item.trunc;
                    do @(posedge vif.clk); while(!vif.in_ready);
                end
                expected.write(item);
                @(negedge vif.clk); vif.in_valid=0;
                seq_item_port.item_done();
            end
        endtask
    endclass
    class mx_monitor extends uvm_monitor;
        `uvm_component_utils(mx_monitor)
        virtual mx_if vif;
        mx_scoreboard sb;
        function new(string name,uvm_component parent); super.new(name,parent); endfunction
        task run_phase(uvm_phase phase);
            bit stalled; bit [36:0] payload;
            forever begin
                @(posedge vif.clk);
                if(vif.rst) stalled=0;
                else begin
                    if(stalled && (!vif.out_valid || {vif.out_flags,vif.out_data}!==payload))
                        `uvm_fatal("STALL","Output changed under backpressure")
                    if(vif.out_valid && vif.out_ready) sb.check_result(vif.out_data,vif.out_flags);
                    stalled=vif.out_valid && !vif.out_ready;
                    payload={vif.out_flags,vif.out_data};
                end
            end
        endtask
    endclass
    class mx_test extends uvm_test;
        `uvm_component_utils(mx_test)
        uvm_sequencer #(mx_item) sequencer;
        mx_driver driver; mx_monitor monitor; mx_scoreboard sb;
        virtual mx_if vif;
        function new(string name,uvm_component parent); super.new(name,parent); endfunction
        function void build_phase(uvm_phase phase);
            super.build_phase(phase);
            if(!uvm_config_db#(virtual mx_if)::get(this,"","vif",vif)) `uvm_fatal("VIF","Missing interface")
            sequencer=new("sequencer",this);
            driver=mx_driver::type_id::create("driver",this);
            monitor=mx_monitor::type_id::create("monitor",this);
            sb=mx_scoreboard::type_id::create("scoreboard",this);
            driver.vif=vif; monitor.vif=vif; monitor.sb=sb;
        endfunction
        function void connect_phase(uvm_phase phase);
            driver.seq_item_port.connect(sequencer.seq_item_export);
            driver.expected.connect(sb.expected.analysis_export);
        endfunction
        task run_phase(uvm_phase phase);
            mx_sequence seq=mx_sequence::type_id::create("sequence");
            phase.raise_objection(this);
            seq.start(sequencer);
            repeat(40) @(posedge vif.clk);
            if(sb.checked!=seq.count || sb.expected.used()!=0) `uvm_fatal("DRAIN","Missing results")
            `uvm_info("MX_PASS",$sformatf("checked=%0d",sb.checked),UVM_NONE)
            phase.drop_objection(this);
        endtask
    endclass
endpackage
module mx_uvm_top #(parameter integer PIPE_STAGES=5);
    import uvm_pkg::*; import mx_uvm_pkg::*;
    bit clk=0; always #5 clk=~clk;
    mx_if bus(clk);
    mx_pe #(.LANES(8),.PIPE_STAGES(PIPE_STAGES)) dut(.clk(clk),.rst(bus.rst),
        .in_valid(bus.in_valid),.in_ready(bus.in_ready),.in_a(bus.in_a),.in_b(bus.in_b),
        .in_scale_a(bus.in_scale_a),.in_scale_b(bus.in_scale_b),.in_fmt(bus.in_fmt),
        .in_bf16(bus.in_bf16),.in_trunc(bus.in_trunc),.out_valid(bus.out_valid),
        .out_ready(bus.out_ready),.out_data(bus.out_data),.out_flags(bus.out_flags));
    bit [15:0] lfsr=16'hace1;
    always @(negedge clk) begin
        lfsr={lfsr[14:0],lfsr[15]^lfsr[13]^lfsr[12]^lfsr[10]};
        bus.out_ready=|lfsr[2:0];
    end
    initial begin repeat(4) @(negedge clk); bus.rst=0; end
    initial begin
        uvm_config_db#(virtual mx_if)::set(null,"uvm_test_top","vif",bus);
        run_test("mx_test");
    end
    initial begin #2000000; $fatal(1,"UVM watchdog expired"); end
endmodule
