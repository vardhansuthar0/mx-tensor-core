logic [63:0] p;
logic [69:0] q,expected;
logic rn,rp,rm,ra,negative;
logic [1:0] ak,bk;
integer reference_grid;
always_comb begin
p=64'(element_magnitude(in_a,fmt))*64'(element_magnitude(in_b,fmt));
case(fmt)0:reference_grid=14;1:reference_grid=0;2:reference_grid=24;3:reference_grid=26;4:reference_grid=30;default:reference_grid=0;endcase
q=(70'(p)>>(reference_grid+int'(trunc)))<<(reference_grid+int'(trunc));
negative=element_negative(in_a,fmt)^element_negative(in_b,fmt);
ak=element_kind(in_a,fmt);bk=element_kind(in_b,fmt);
rn=poison;rp=0;rm=0;ra=0;expected=0;
if(!poison) begin
if(ak==2 || bk==2) rn=1;
else if(ak==1 || bk==1) begin
if((ak==0 && element_magnitude(in_a,fmt)==0)||(bk==0 && element_magnitude(in_b,fmt)==0))rn=1;
else if(negative)rm=1;else rp=1;
end else begin expected=negative?-q:q;ra=(70'(p)!=q);end
end
end
assign ok=({nan_comb,pos_comb,neg_comb,approx_comb,(products_comb ^ 70'(negative_control))}=={rn,rp,rm,ra,expected});
