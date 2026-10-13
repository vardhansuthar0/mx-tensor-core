module protocol_proof(input clk);
    (* anyseq *) reg rst,in_valid,out_ready;
    (* anyseq *) reg [63:0] in_a,in_b;
    (* anyseq *) reg [7:0] sa,sb;
    (* anyseq *) reg [2:0] fmt;
    (* anyseq *) reg bf;
    (* anyseq *) reg [4:0] trunc;
    wire in_ready,out_valid;
    wire [31:0] data;
    wire [4:0] flags;
    mx_pe #(.LANES(8),.PIPE_STAGES(4)) dut(clk,rst,in_valid,in_ready,in_a,in_b,sa,sb,fmt,bf,trunc,out_valid,out_ready,data,flags);
    reg past_valid=0;
    reg was_rst,was_stall;
    reg [36:0] last_payload;
    always @(posedge clk) begin
        past_valid<=1;
        was_rst<=rst;
        was_stall<=out_valid && !out_ready;
        last_payload<={flags,data};
    end
    always @* begin
        if(!past_valid) assume(rst);
        if(past_valid && was_rst) assert(!out_valid);
        if(past_valid && !was_rst && was_stall) begin
            assert(out_valid);
            assert({flags,data}==last_payload);
        end
        if(rst) assert(!in_ready);
    end
endmodule
