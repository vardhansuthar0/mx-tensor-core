"""Optional documentation builder: pip install reportlab pypdf."""
import json,pathlib,re
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'docs';S=json.loads((ROOT/'reports/status.json').read_text())
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
pdfmetrics.registerFont(TTFont('DX','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DX-Bold','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
pdfmetrics.registerFontFamily('DX',normal='DX',bold='DX-Bold',italic='DX',boldItalic='DX-Bold')
navy=colors.HexColor('#15334a');teal=colors.HexColor('#087d86');gray=colors.HexColor('#526170')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyX',fontName='DX',fontSize=9.5,leading=13.1,textColor=navy,spaceAfter=7))
styles.add(ParagraphStyle(name='SmallX',parent=styles['BodyX'],fontSize=8,leading=10.5))
styles.add(ParagraphStyle(name='HeadX',fontName='DX-Bold',fontSize=13,leading=16,textColor=teal,spaceBefore=10,spaceAfter=7))
styles.add(ParagraphStyle(name='TitleX',fontName='DX-Bold',fontSize=27,leading=30,textColor=navy,spaceAfter=10))
styles.add(ParagraphStyle(name='KickerX',fontName='DX-Bold',fontSize=9,leading=12,textColor=teal,spaceAfter=9))
def P(text,style='BodyX'):return Paragraph(text,styles[style])
def table(rows,widths=None):
 rows=[[P(escape(str(x)),'SmallX') for x in row] for row in rows]
 t=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4eff2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),1,teal),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#d4dce3')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
 return t

def footer(c,d):
 c.setStrokeColor(teal);c.line(48,42,564,42)
 c.setFont('DX',8);c.setFillColor(gray)
 c.drawString(48,29,'MX TENSOR DATAPATH  |  VERIFIED RTL MILESTONE')
 c.drawRightString(564,29,str(d.page))
def save(name,story):
 SimpleDocTemplate(str(OUT/name),pagesize=letter,rightMargin=48,leftMargin=48,topMargin=42,bottomMargin=55,title=name.replace('-',' ').replace('.pdf',''),author='MX tensor project').build(story,onFirstPage=footer,onLaterPages=footer)

story=[P('PUBLIC-SPECIFICATION HARDWARE PROJECT','KickerX'),P('MX tensor datapath','TitleX'),
 P('Five element formats. Exact arithmetic. Reproducible verification.','HeadX'),
 P('A parameterizable SystemVerilog block-dot processing element (PE) computes 32-element microscaled dot products. A broadcast array combines up to 16 PEs into a 4 x 4 output tile. This milestone implements and verifies RTL; SKY130 area, timing and power have <b>not</b> been measured.'),
 P('Architecture and interface','HeadX'),
 table([['Capability','Implemented contract'],['Element formats','FP8 E4M3/E5M2, FP6 E3M2/E2M3, FP4 E2M1'],['Scale and block size','Two E8M0 scales per block pair; 32 elements per block'],['Parallelism / depth','8, 16 or 32 lanes; 3, 4 or 5 pipeline stages'],['Arithmetic','Exact 70-bit signed accumulator or per-product TRUNC(n)'],['Outputs','FP32 or BF16, directly rounded ties-to-even; exception flags'],['Integration','Ready/valid streams, APB control, sticky flags, retired-tile counter']],[137,379]),
 P('Four-stage baseline','HeadX'),
 P('<b>Decode</b> extracts finite significands and specials. <b>Multiply</b> uses at most 4 x 4-bit significand products and aligns them on a common binary grid. <b>Reduce</b> uses a recursive carry-save tree and accumulates earlier beats. <b>Convert</b> normalizes and rounds once to the selected destination.'),
 P('A global pipeline enable freezes all stages when the output stalls. The no-bubble test demonstrates one completed block every 1, 2 or 4 cycles for 32, 16 or 8 lanes, respectively. These are cycle counts, not measured clock frequencies.'),
 P('The key numerical decision','HeadX'),
 P('Exact summation avoids order-dependent intermediate rounding. Including the sign bit, the format-native 32-term accumulator widths are 42, 70, 24, 18 and 14 bits for E4M3, E5M2, E3M2, E2M3 and E2M1. Runtime format selection therefore retains a 70-bit datapath. Runtime truncation explores accuracy; it does not claim an area reduction.'),
 P('TRUNC(n) removes low magnitude bits before applying the product sign, so negative values truncate toward zero. BF16 is rounded directly from the wide sum, avoiding FP32-to-BF16 double rounding. Subnormals are preserved. NaN scales ignore element encodings and poison the block.'),
 PageBreak(),P('VERIFICATION AND EVIDENCE','KickerX'),P('What actually passed','TitleX'),
 table([['Check','Recorded result'],['Reference model','656 element encodings cross-checked against ml_dtypes; 44,000 rounding checks'],['PE regression',f"{S['pe_blocks_checked']:,} checked block outputs across 9 lane/depth configurations"],['Functional coverage','160/160 declared contract bins + 7/7 rounding classes in every configuration'],['Array and APB',f"{S['array_tiles_checked']} tiles / {S['array_results_checked']} PE results across 1x1, 2x2 and 4x4 arrays"],['Mutation campaign',f"{S['mutations']['killed']}/{S['mutations']['total']} named RTL mutants killed; passing baseline required"],['Formal','70-bit CSA compressor identity; unbounded PE reset and stalled-output properties']],[137,379]),
 P('How the evidence is produced','HeadX'),
 P('A pyuvm environment, agent and scoreboard use a cocotb BFM to reconstruct transactions from accepted DUT pins. An integer-only reference predicts data and flags. Coverage is awarded only after a matching result retires. Directed sequences close boundary bins; seeded random tests vary input values, scales, truncation, bubbles and backpressure.'),
 P('The declared bins cross format, output, exact/TRUNC(1) mode and eight scenarios, plus seven rounding classes. Full coverage of this finite plan is <b>not</b> exhaustive arithmetic or code coverage. Formal results cover the named structural/protocol properties, not end-to-end floating-point equivalence.'),
 P('A real bug found during development','HeadX'),
 P('A NaN scale produced the expected quiet NaN but also raised an approximation flag from discarded element bits. The scoreboard caught the flags mismatch. The RTL now suppresses element-derived approximation events when a scale is NaN. Planted defects separately exercise scale bias, subnormals, E4M3 specials, sign, ties, NaN scales, multi-beat summation, truncation and backpressure.'),
 P('Reproduce and finish the physical milestone','HeadX'),
 P('<b>After dependency setup: <font name="Courier">make reproduce</font></b>. Raw logs, coverage, mutation results, tool versions and source hashes are in reports/. The OpenLane configuration and physical preflight are provided; a SKY130 PDK and complete OpenROAD/OpenSTA environment are still required. Routed parasitics and audited switching activity must accompany any future timing/power claim.'),
 P('Public-specification scope','HeadX'),
 P("NVIDIA's internal tensor-core designs are proprietary. This project is built only from public specifications (the OCP Microscaling Formats spec and standard IEEE-754 behavior), so it shows the same class of problem without claiming to replicate any real product.",'SmallX'),
 P('Reference: OCP Microscaling Formats v1.0 (September 2023), sections 5.2-5.4 and 6.1. Source link and exact contract: docs/microarchitecture.md. Physical and coverage limitations: physical/README.md and docs/verification-plan.md.','SmallX')]
save('mx-tensor-writeup.pdf',story)

styles['BodyX'].fontSize=9
styles['BodyX'].leading=12
styles['TitleX'].fontSize=23
styles['TitleX'].leading=27
# Render the complete normative Markdown spec into two/three readable pages.
lines=(OUT/'microarchitecture.md').read_text().splitlines();story=[];i=0
while i<len(lines):
 line=lines[i]
 if not line.strip():i+=1;continue
 if line.startswith('TRUNC(n),'):
  story.append(PageBreak())
 if line.startswith('## 2.'):
  story.append(Spacer(1,4))
 if line.startswith('# '):story.append(P(escape(line[2:]),'TitleX'));i+=1;continue
 if line.startswith('## '):story.append(P(escape(line[3:]),'HeadX'));i+=1;continue
 if line.startswith('|'):
  rows=[]
  while i<len(lines) and lines[i].startswith('|'):
   if not re.match(r'^\|[-| ]+\|$',lines[i]):rows.append([x.strip() for x in lines[i].strip('|').split('|')])
   i+=1
  widths=[516/len(rows[0])]*len(rows[0])
  if len(rows[0])==7:widths=[25,53,44,31,54,86,223]
  if len(rows[0])==4:widths=[74,64,282,96]
  story.append(table(rows,widths));story.append(Spacer(1,7));continue
 para=[]
 while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|')):
  para.append(lines[i]);i+=1
 text=' '.join(para)
 text=escape(text)
 text=re.sub(r'(https://[^ ]+)',r'<link href="\1" color="#087d86">OCP MX v1.0 specification</link>',text)
 story.append(P(text))
save('mx-microarchitecture.pdf',story)

bullets=[
 'Implemented a SystemVerilog MX block-dot datapath supporting five FP8/FP6/FP4 formats, 8/16/32 lanes and 3/4/5 pipeline stages, with exact 70-bit accumulation, FP32/BF16 rounding and a 4x4 APB-controlled tile array.',
 f"Built a pyuvm/cocotb verification environment checking {S['pe_blocks_checked']:,} block outputs across nine configurations; closed 160/160 declared functional bins and 7/7 rounding classes per configuration, with 656 element encodings independently cross-checked.",
 f"Detected {S['mutations']['killed']}/{S['mutations']['total']} planted RTL defects and proved a 70-bit CSA identity plus unbounded reset/backpressure properties using Yosys SAT; automated regressions, formal checks and mutation testing behind one Make command."
]
(OUT/'resume-bullets.md').write_text('# Resume bullets - measured RTL milestone\n\n'+'\n\n'.join('- '+x for x in bullets)+'\n\nDo not add SKY130 area, MHz, power, routed-layout, full-UVM or end-to-end arithmetic-formal claims until those milestones are complete.\n')
from pypdf import PdfReader
for name in ['mx-tensor-writeup.pdf','mx-microarchitecture.pdf']:
 print(name,len(PdfReader(OUT/name).pages),'pages')
assert len(PdfReader(OUT/'mx-tensor-writeup.pdf').pages)==2
assert 2<=len(PdfReader(OUT/'mx-microarchitecture.pdf').pages)<=3
