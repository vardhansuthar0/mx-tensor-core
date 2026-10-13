module mx_csa #(parameter integer N=32, W=70)(input wire [N*W-1:0] terms, output wire [W-1:0] sum);
    generate
        if (N==1) begin: one
            assign sum = terms;
        end else if (N==2) begin: two
            assign sum = terms[0+:W] + terms[W+:W];
        end else begin: many
            localparam integer G=N/3, R=N%3, NEXT=2*G+R;
            wire [NEXT*W-1:0] reduced;
            for (genvar i=0;i<G;i=i+1) begin: group3
                wire [W-1:0] a=terms[(3*i)*W+:W], b=terms[(3*i+1)*W+:W], c=terms[(3*i+2)*W+:W];
                assign reduced[(2*i)*W+:W] = a ^ b ^ c;
                assign reduced[(2*i+1)*W+:W] = ((a&b)|(a&c)|(b&c)) << 1;
            end
            for (genvar j=0;j<R;j=j+1) begin: remainder
                assign reduced[(2*G+j)*W+:W]=terms[(3*G+j)*W+:W];
            end
            mx_csa #(.N(NEXT), .W(W)) next_level(reduced,sum);
        end
    endgenerate
endmodule
