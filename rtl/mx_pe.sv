module mx_pe #(parameter integer LANES=32, PIPE_STAGES=4)(
    input wire clk, rst, in_valid, output wire in_ready,
    input wire [LANES*8-1:0] in_a, in_b,
    input wire [7:0] in_scale_a, in_scale_b,
    input wire [2:0] in_fmt, input wire in_bf16, input wire [4:0] in_trunc,
    output logic out_valid, input wire out_ready,
    output logic [31:0] out_data, output logic [4:0] out_flags
);
    localparam integer BEATS=32/LANES;
    typedef struct packed { logic signbit, nanbit, infbit; logic [3:0] sig; logic signed [6:0] exponent; } dec_t;
    typedef struct packed { logic last, bf16, poison; logic [4:0] trunc; logic [5:0] grid; logic signed [9:0] scale; } meta_t;
    function automatic dec_t decode(input logic [7:0] code, input logic [2:0] fmt);
        integer eb, mb, bias, ex, fr;
        dec_t d;
        begin
            eb=4; mb=3; bias=7;
            case(fmt)
                1: begin eb=5; mb=2; bias=15; end
                2: begin eb=3; mb=2; bias=3; end
                3: begin eb=2; mb=3; bias=1; end
                4: begin eb=2; mb=1; bias=1; end
                default: begin end
            endcase
            ex=(int'(code)>>mb)&((1<<eb)-1); fr=int'(code)&((1<<mb)-1); d='0;
            d.signbit=1'((int'(code)>>(eb+mb))&1);
            d.sig=4'(fr+((ex!=0)?(1<<mb):0));
            d.exponent=7'(((ex!=0)?ex:1)-bias-mb);
            d.nanbit=(fmt==0 && ex==15 && fr==7)||(fmt==1 && ex==31 && fr!=0);
            d.infbit=(fmt==1 && ex==31 && fr==0);
            decode=d;
        end
    endfunction
    function automatic [5:0] grid_for(input logic [2:0] fmt);
        case(fmt)
            0: grid_for=14; 1: grid_for=0; 2: grid_for=24;
            3: grid_for=26; 4: grid_for=30; default: grid_for=0;
        endcase
    endfunction
    function automatic integer leading70(input logic [69:0] value);
        logic [127:0] search;
        integer index;
        begin
            search={58'b0,value}; index=0;
            for(integer step=64;step>0;step=step/2) begin
                if(|(search>>step)) begin search=search>>step; index=index+step; end
            end
            leading70=index;
        end
    endfunction
    // Keep the signed-total interface for equivalence; magnitude is precomputed.
    /* verilator lint_off UNUSEDSIGNAL */
    function automatic [36:0] convert(input logic signed [69:0] total, input logic bf16, input logic signed [9:0] scale,
        input logic nanbit, posinf, neginf, approx, input logic [69:0] magnitude, input logic [6:0] leading);
    /* verilator lint_on UNUSEDSIGNAL */
        logic [69:0] mag, kept, sticky_terms;
        logic signbit, guardbit, sticky, lost;
        logic [31:0] bits;
        logic [4:0] flags;
        integer lead, p, expo, shift, exfield;
        begin
            signbit=total[69]; mag=magnitude;
            p=bf16?8:24; bits=0; flags={approx,4'b0000};
            lead=0; expo=0; shift=0; exfield=0; guardbit=0; sticky=0; lost=0; kept=0; sticky_terms=0;
            if (nanbit || (posinf && neginf)) begin
                bits=bf16?32'h00007fc0:32'h7fc00000; flags[3]=1;
            end else if(posinf || neginf) begin
                bits=(32'(neginf)<<(p+7)) | (32'd255<<(p-1));
            end else if(mag!=0) begin
                lead=int'(leading);
                expo=lead+int'($signed(scale))-32; shift=lead-(p-1);
                if(expo < -126) shift=-126-(p-1)-(int'($signed(scale))-32);
                if(shift>0) begin
                    kept=mag>>shift;
                    for(integer i=0;i<70;i=i+1) begin
                        if(i==shift-1) guardbit=mag[i];
                        sticky_terms[i]=(i<shift-1) && mag[i];
                    end
                    sticky=|sticky_terms;
                    lost=guardbit|sticky;
                    if(guardbit && (sticky || kept[0])) kept=kept+70'd1;
                end else kept=mag<<(-shift);
                flags[0]=lost;
                if(expo < -126) begin
                    if(kept >= (70'd1<<(p-1))) exfield=1;
                    else begin exfield=0; flags[1]=lost; end
                end else begin
                    if(kept >= (70'd1<<p)) begin kept=kept>>1; expo=expo+1; end
                    exfield=expo+127;
                end
                if(exfield>=255) begin
                    bits=(32'(signbit)<<(p+7)) | (32'd255<<(p-1)); flags[2]=1; flags[0]=1;
                end else bits=(32'(signbit)<<(p+7)) | (32'(exfield)<<(p-1)) | (32'(kept)&((32'd1<<(p-1))-1));
            end
            convert={flags,bits};
        end
    endfunction
    wire advance=!out_valid || out_ready;
    assign in_ready=advance && !rst;
    logic [2:0] beat, held_fmt;
    meta_t held_meta, input_meta;
    wire [2:0] active_fmt=(beat==0)?in_fmt:held_fmt;
    always_comb begin
        input_meta=held_meta;
        if(beat==0) begin
            input_meta.bf16=in_bf16; input_meta.trunc=in_trunc; input_meta.grid=grid_for(in_fmt);
            input_meta.scale=10'(int'(in_scale_a)+int'(in_scale_b)-254);
            input_meta.poison=(in_scale_a==255)||(in_scale_b==255)||(in_fmt>4);
        end
        input_meta.last=(int'(beat)==BEATS-1);
    end
    always_ff @(posedge clk) begin
        if(rst) begin beat<=0; held_fmt<=0; held_meta<='0; end
        else if(in_valid && in_ready) begin
            if(beat==0) begin held_fmt<=in_fmt; held_meta<=input_meta; end
            if(int'(beat)==BEATS-1) beat<=0; else beat<=beat+1'b1;
        end
    end
    dec_t da[LANES], db[LANES];
    meta_t m1;
    logic v1;
    generate
        if(PIPE_STAGES==3) begin: bypass_decode
            always_comb begin
                v1=in_valid; m1=input_meta;
                for(integer i=0;i<LANES;i=i+1) begin
                    da[i]=decode(in_a[8*i+:8],active_fmt); db[i]=decode(in_b[8*i+:8],active_fmt);
                end
            end
        end else begin: register_decode
            always_ff @(posedge clk) begin
                if(rst) begin
                    v1<=0; m1<='0;
                    for(integer i=0;i<LANES;i=i+1) begin da[i]<='0; db[i]<='0; end
                end else if(advance) begin
                    v1<=in_valid; m1<=input_meta;
                    for(integer i=0;i<LANES;i=i+1) begin
                        da[i]<=decode(in_a[8*i+:8],active_fmt); db[i]<=decode(in_b[8*i+:8],active_fmt);
                    end
                end
            end
        end
    endgenerate
    logic [LANES*70-1:0] products_comb, products;
    logic nan_comb, pos_comb, neg_comb, approx_comb, nan2, pos2, neg2, approx2, v2;
    typedef struct packed { logic last, bf16; logic signed [9:0] scale; } mul_meta_t;
    typedef struct packed { logic bf16; logic signed [9:0] scale; } out_meta_t;
    mul_meta_t m2;
    logic [69:0] mag, clipped;
    logic [7:0] mant_product;
    integer alignment, cut;
    always_comb begin
        products_comb='0; nan_comb=m1.poison; pos_comb=0; neg_comb=0; approx_comb=0;
        mag=0; clipped=0; mant_product=0; alignment=0; cut=0;
        for(integer i=0;i<LANES;i=i+1) begin
            if(da[i].nanbit || db[i].nanbit) nan_comb=1;
            else if(da[i].infbit || db[i].infbit) begin
                if((!da[i].infbit && da[i].sig==0)||(!db[i].infbit && db[i].sig==0)) nan_comb=1;
                else if(da[i].signbit ^ db[i].signbit) neg_comb=1;
                else pos_comb=1;
            end else begin
                mant_product=da[i].sig * db[i].sig;
                alignment=int'($signed(da[i].exponent))+int'($signed(db[i].exponent))+32;
                mag=70'(mant_product)<<alignment;
                cut=int'(m1.grid)+int'(m1.trunc); clipped=(mag>>cut)<<cut;
                approx_comb=approx_comb|(mag!=clipped);
                products_comb[70*i+:70]=(da[i].signbit ^ db[i].signbit)?-clipped:clipped;
            end
        end
        // A NaN scale ignores element encodings, including approximation events.
        if(m1.poison) begin products_comb='0; pos_comb=0; neg_comb=0; approx_comb=0; end
    end
    always_ff @(posedge clk) begin
        if(rst) begin v2<=0; m2<='0; products<=0; nan2<=0; pos2<=0; neg2<=0; approx2<=0; end
        else if(advance) begin
            v2<=v1; m2<={m1.last,m1.bf16,m1.scale}; products<=products_comb;
            nan2<=nan_comb; pos2<=pos_comb; neg2<=neg_comb; approx2<=approx_comb;
        end
    end
    wire [69:0] lane_sum;
    mx_csa #(.N(LANES),.W(70)) tree(products,lane_sum);
    logic signed [69:0] running, sum3;
    logic run_nan,run_pos,run_neg,run_approx, nan3,pos3,neg3,approx3,v3;
    out_meta_t m3;
    always_ff @(posedge clk) begin
        if(rst) begin
            running<=0; sum3<=0; v3<=0; m3<='0;
            run_nan<=0; run_pos<=0; run_neg<=0; run_approx<=0;
            nan3<=0; pos3<=0; neg3<=0; approx3<=0;
        end else if(advance) begin
            v3<=v2 && m2.last;
            if(v2) begin
                if(m2.last) begin
                    sum3<=running+$signed(lane_sum); m3<={m2.bf16,m2.scale};
                    nan3<=run_nan|nan2; pos3<=run_pos|pos2; neg3<=run_neg|neg2; approx3<=run_approx|approx2;
                    running<=0; run_nan<=0; run_pos<=0; run_neg<=0; run_approx<=0;
                end else begin
                    running<=running+$signed(lane_sum);
                    run_nan<=run_nan|nan2; run_pos<=run_pos|pos2; run_neg<=run_neg|neg2; run_approx<=run_approx|approx2;
                end
            end
        end
    end
    logic signed [69:0] sum4;
    logic nan4,pos4,neg4,approx4,v4;
    out_meta_t m4;
    logic [69:0] converter_mag;
    logic [6:0] converter_lead;
    // Preserve parallel-prefix levels through synthesis. The baseline mapped
    // two's-complement magnitude to a long chain of shared OR prefixes.
    for(genvar level=0;level<8;level=level+1) begin: magnitude_tree
        (* keep = 1 *) wire [69:0] prefix;
        if(level==0) begin: first_level
            assign prefix=sum3;
        end else begin: next_level
            assign prefix=magnitude_tree[level-1].prefix | (magnitude_tree[level-1].prefix << (1<<(level-1)));
        end
    end
    wire [69:0] completed_mag=$unsigned(sum3) ^ ((magnitude_tree[7].prefix<<1) & {70{sum3[69]}});
    wire [6:0] completed_lead=7'(leading70(completed_mag));
    // End normalization network.
    generate
        if(PIPE_STAGES==5) begin: extra_stage
            always_ff @(posedge clk) begin
                if(rst) begin converter_mag<=0; converter_lead<=0; sum4<=0; m4<='0; nan4<=0; pos4<=0; neg4<=0; approx4<=0; v4<=0; end
                else if(advance) begin
                    converter_mag<=completed_mag; converter_lead<=completed_lead; sum4<=sum3; m4<=m3; nan4<=nan3; pos4<=pos3; neg4<=neg3; approx4<=approx3; v4<=v3;
                end
            end
        end else begin: no_extra_stage
            always_comb begin converter_mag=completed_mag; converter_lead=completed_lead; sum4=sum3; m4=m3; nan4=nan3; pos4=pos3; neg4=neg3; approx4=approx3; v4=v3; end
        end
    endgenerate
    always_ff @(posedge clk) begin
        if(rst) begin out_valid<=0; out_data<=0; out_flags<=0; end
        else if(advance) begin out_valid<=v4; if(v4) {out_flags,out_data}<=convert(sum4,m4.bf16,m4.scale,nan4,pos4,neg4,approx4,converter_mag,converter_lead); end
    end
`ifndef SYNTHESIS
    initial begin
        assert(LANES==8 || LANES==16 || LANES==32) else $fatal(1,"Unsupported LANES");
        assert(PIPE_STAGES>=3 && PIPE_STAGES<=5) else $fatal(1,"Unsupported PIPE_STAGES");
    end
    assert property (@(posedge clk) disable iff(rst) out_valid && !out_ready |=> rst || (out_valid && $stable({out_data,out_flags})));
    assert property (@(posedge clk) rst |=> !out_valid);
    assert property (@(posedge clk) disable iff(rst) int'(beat) < BEATS);
`endif
endmodule
