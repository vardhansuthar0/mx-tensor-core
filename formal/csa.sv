module csa_proof(input [69:0] a,b,c);
    wire [69:0] sum;
    mx_csa #(.N(3),.W(70)) dut({c,b,a},sum);
    always @* assert(sum==a+b+c);
endmodule
