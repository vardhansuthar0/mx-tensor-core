// Integer RNE specification: choose destination quantum, divide exactly,
// compare the integer remainder with half a quantum, then encode the result.
// Uses remainder comparison rather than the implementation's guard/sticky scan.
function automatic [36:0] specification_convert(
    input logic signed [69:0] value, input logic bf16,
    input logic signed [9:0] block_scale,
    input logic nan_input, positive_inf, negative_inf, approximate);
    logic [69:0] magnitude, quotient, remainder, half;
    logic [31:0] result;
    logic [4:0] exceptions;
    logic negative, discarded;
    integer fraction_bits, source_power, top_power, quantum_power, distance, leading, exponent_field;
    begin
        negative=value[69]; magnitude=negative ? $unsigned(-value) : $unsigned(value);
        fraction_bits=bf16 ? 7 : 23;
        source_power=int'($signed(block_scale))-32;
        leading=0;top_power=0;quantum_power=0;distance=0;exponent_field=0;
        quotient=0;remainder=0;half=0;discarded=0;
        result=0;exceptions={approximate,4'b0};
        if(nan_input || (positive_inf && negative_inf)) begin
            result=bf16 ? 32'h7fc0 : 32'h7fc00000;exceptions[3]=1;
        end else if(positive_inf || negative_inf) begin
            result=(32'(negative_inf)<<(fraction_bits+8)) | (32'd255<<fraction_bits);
        end else if(magnitude!=0) begin
            for(integer bit_index=0;bit_index<70;bit_index=bit_index+1)
                if(magnitude[bit_index]) leading=bit_index;
            top_power=leading+source_power;
            if(top_power < -126) top_power=-126;
            quantum_power=top_power-fraction_bits;
            distance=quantum_power-source_power;
            if(distance>70) begin quotient=0;discarded=1; end
            else if(distance>0) begin
                quotient=magnitude>>distance;
                remainder=magnitude-(quotient<<distance);
                half=70'd1<<(distance-1);
                discarded=(remainder!=0);
                if(remainder>half || (remainder==half && quotient[0])) quotient=quotient+70'd1;
            end else quotient=magnitude<<(-distance);
            if(quotient >= (70'd1<<(fraction_bits+1))) begin quotient=quotient>>1;top_power=top_power+1;end
            exceptions[0]=discarded;
            if(top_power>127) begin
                result=(32'(negative)<<(fraction_bits+8)) | (32'd255<<fraction_bits);
                exceptions[2]=1;exceptions[0]=1;
            end else begin
                if(quotient >= (70'd1<<fraction_bits)) exponent_field=top_power+127;
                else begin exponent_field=0;exceptions[1]=discarded;end
                result=(32'(negative)<<(fraction_bits+8)) | (32'(exponent_field)<<fraction_bits) | (32'(quotient)&((32'd1<<fraction_bits)-1));
            end
        end
        specification_convert={exceptions,result};
    end
endfunction
