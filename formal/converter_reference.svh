// Frozen converter from baseline 835e63e; independent equivalence reference.
    function automatic [36:0] reference_convert(input logic signed [69:0] total, input logic bf16, input logic signed [9:0] scale,
        input logic nanbit, posinf, neginf, approx);
        logic [69:0] mag, kept;
        logic signbit, guardbit, sticky, lost;
        logic [31:0] bits;
        logic [4:0] flags;
        integer lead, p, expo, shift, exfield;
        begin
            signbit=total[69]; mag=signbit ? $unsigned(-total) : $unsigned(total);
            p=bf16?8:24; bits=0; flags={approx,4'b0000};
            lead=0; expo=0; shift=0; exfield=0; guardbit=0; sticky=0; lost=0; kept=0;
            if (nanbit || (posinf && neginf)) begin
                bits=bf16?32'h00007fc0:32'h7fc00000; flags[3]=1;
            end else if(posinf || neginf) begin
                bits=(32'(neginf)<<(p+7)) | (32'd255<<(p-1));
            end else if(mag!=0) begin
                for(integer i=0;i<70;i=i+1) if(mag[i]) lead=i;
                expo=lead+int'($signed(scale))-32; shift=lead-(p-1);
                if(expo < -126) shift=-126-(p-1)-(int'($signed(scale))-32);
                if(shift>0) begin
                    kept=mag>>shift;
                    for(integer i=0;i<70;i=i+1) begin
                        if(i==shift-1) guardbit=mag[i];
                        if(i<shift-1) sticky=sticky|mag[i];
                    end
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
            reference_convert={flags,bits};
        end
    endfunction
