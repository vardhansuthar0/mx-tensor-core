function automatic [31:0] element_magnitude(input [7:0] code,input [2:0] fmt);
    integer e,f,shift,mantissa;
    begin
        e=0;f=0;shift=0;mantissa=0;
        case(fmt)
            0: begin e=(int'(code)>>3)&15;f=int'(code)&7;mantissa=e==0?f:8+f;shift=e==0?7:e+6;end
            1: begin e=(int'(code)>>2)&31;f=int'(code)&3;mantissa=e==0?f:4+f;shift=e==0?0:e-1;end
            2: begin e=(int'(code)>>2)&7;f=int'(code)&3;mantissa=e==0?f:4+f;shift=e==0?12:e+11;end
            3: begin e=(int'(code)>>3)&3;f=int'(code)&7;mantissa=e==0?f:8+f;shift=e==0?13:e+12;end
            4: begin e=(int'(code)>>1)&3;f=int'(code)&1;mantissa=e==0?f:2+f;shift=e==0?15:e+14;end
            default: begin end
        endcase
        element_magnitude=32'(mantissa)<<shift;
    end
endfunction
function automatic element_negative(input [7:0] code,input [2:0] fmt);
    case(fmt)
        0,1:element_negative=code[7];
        2,3:element_negative=code[5];
        4:element_negative=code[3];
        default:element_negative=0;
    endcase
endfunction
function automatic [1:0] element_kind(input [7:0] code,input [2:0] fmt);
    if(fmt==0 && (code&8'h7f)==8'h7f) element_kind=2;
    else if(fmt==1 && (code&8'h7c)==8'h7c) element_kind=(code[1:0]==0)?1:2;
    else element_kind=0;
endfunction
function automatic [36:0] reference_dot(input [255:0] avec,bvec,input [2:0] fmt,input [7:0] sa,sb,input bf,input [4:0] trunc);
    logic signed [69:0] total;
    logic [63:0] product;
    logic [69:0] quantized;
    logic [31:0] am,bm;
    logic [7:0] ac,bc;
    logic [1:0] ak,bk;
    logic nanbit,posinf,neginf,approx,negative;
    integer cut,grid;
    logic signed [9:0] scale;
    begin
        total=0;nanbit=0;posinf=0;neginf=0;approx=0;product=0;quantized=0;
        am=0;bm=0;ac=0;bc=0;ak=0;bk=0;negative=0;
        case(fmt) 0:grid=14;1:grid=0;2:grid=24;3:grid=26;4:grid=30;default:grid=0;endcase
        cut=grid+int'(trunc);scale=10'(int'(sa)+int'(sb)-254);
        if(sa==255 || sb==255 || fmt>4) nanbit=1;
        else for(integer lane=0;lane<32;lane=lane+1) begin
            ac=avec[lane*8+:8];bc=bvec[lane*8+:8];
            am=element_magnitude(ac,fmt);bm=element_magnitude(bc,fmt);
            ak=element_kind(ac,fmt);bk=element_kind(bc,fmt);
            negative=element_negative(ac,fmt)^element_negative(bc,fmt);
            if(ak==2 || bk==2) nanbit=1;
            else if(ak==1 || bk==1) begin
                if((ak==0 && am==0)||(bk==0 && bm==0)) nanbit=1;
                else if(negative) neginf=1;else posinf=1;
            end else begin
                product=64'(am)*64'(bm);
                quantized=(70'(product)>>cut)<<cut;
                approx=approx|(70'(product)!=quantized);
                total=total+(negative ? -$signed(quantized) : $signed(quantized));
            end
        end
        reference_dot=specification_convert(total,bf,scale,nanbit,posinf,neginf,approx);
    end
endfunction
