// Broadcast array: one atomic MxN output tile per 32-element K block.
module mx_engine #(parameter integer LANES=8, PIPE_STAGES=4, M=4, N=4)(
    input wire clk,rst,
    input wire in_valid, output wire in_ready,
    input wire [M*LANES*8-1:0] in_a,
    input wire [N*LANES*8-1:0] in_b,
    input wire [M*8-1:0] in_scale_a,
    input wire [N*8-1:0] in_scale_b,
    output wire out_valid, input wire out_ready,
    output wire [M*N*32-1:0] out_data,
    output wire [M*N*5-1:0] out_flags,
    input wire psel,penable,pwrite,
    input wire [7:0] paddr,
    input wire [31:0] pwdata,
    output logic [31:0] prdata,
    output wire pready, output logic pslverr
);
    logic [8:0] config_reg;
    logic [4:0] sticky_flags;
    logic [31:0] retired;
    wire [M*N-1:0] pe_ready,pe_valid;
    wire retire=out_valid && out_ready;
    wire access=psel && penable;
    logic [4:0] tile_flags;
    assign in_ready=&pe_ready;
    assign out_valid=&pe_valid;
    assign pready=1;
    always_comb begin
        tile_flags=0;
        for(integer k=0;k<M*N;k=k+1) tile_flags=tile_flags|out_flags[k*5+:5];
        prdata=0;pslverr=0;
        case(paddr)
            8'h00: begin
                prdata={23'b0,config_reg};
                if(pwrite && ((pwdata[2:0]>4)||(|pwdata[31:9]))) pslverr=access;
            end
            8'h04: begin
                prdata={27'b0,sticky_flags};
                if(pwrite && |pwdata[31:5]) pslverr=access;
            end
            8'h08: begin prdata=retired; if(pwrite) pslverr=access; end
            8'h0c: begin prdata={8'(M),8'(N),8'(LANES),8'(PIPE_STAGES)}; if(pwrite) pslverr=access; end
            default: pslverr=access;
        endcase
    end
    always_ff @(posedge clk) begin
        if(rst) begin config_reg<=0;sticky_flags<=0;retired<=0;end
        else begin
            if(access && pwrite && !pslverr && paddr==0) config_reg<=pwdata[8:0];
            if(access && pwrite && !pslverr && paddr==4)
                sticky_flags <= (sticky_flags & ~pwdata[4:0]) | (retire?tile_flags:5'b0);
            else if(retire) sticky_flags<=sticky_flags|tile_flags;
            if(retire) retired<=retired+1'b1;
        end
    end
    generate
        for(genvar r=0;r<M;r=r+1) begin: rows
            for(genvar c=0;c<N;c=c+1) begin: cols
                mx_pe #(.LANES(LANES),.PIPE_STAGES(PIPE_STAGES)) pe(
                    .clk(clk),.rst(rst),.in_valid(in_valid && in_ready),.in_ready(pe_ready[r*N+c]),
                    .in_a(in_a[r*LANES*8+:LANES*8]),.in_b(in_b[c*LANES*8+:LANES*8]),
                    .in_scale_a(in_scale_a[r*8+:8]),.in_scale_b(in_scale_b[c*8+:8]),
                    .in_fmt(config_reg[2:0]),.in_bf16(config_reg[3]),.in_trunc(config_reg[8:4]),
                    .out_valid(pe_valid[r*N+c]),.out_ready(out_ready && out_valid),
                    .out_data(out_data[(r*N+c)*32+:32]),.out_flags(out_flags[(r*N+c)*5+:5])
                );
            end
        end
    endgenerate
`ifndef SYNTHESIS
    initial assert((M==1||M==2||M==4)&&(N==1||N==2||N==4)) else $fatal(1,"Unsupported array");
    assert property (@(posedge clk) disable iff(rst) (pe_valid=='0)||(pe_valid=='1));
`endif
endmodule
