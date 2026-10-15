logic [63:0] p;
logic [69:0] q,expected;
logic rn,rp,rm,ra,negative;
logic [1:0] ak,bk;
always_comb begin
p=64'(element_magnitude(in_a,fmt))*64'(element_magnitude(in_b,fmt));
q=(70'(p)>>(int'(grid_for(fmt))+int'(trunc)))<<(int'(grid_for(fmt))+int'(trunc));
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
