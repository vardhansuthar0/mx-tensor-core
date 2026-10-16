"""Place a local diode beside each pin in an actual antenna violation report.

This changes the layout; it does not waive any antenna or electrical check.
The following legalization, routing, extraction and independent checks remain
necessary. OpenLane's pin-side diode placement utility supplies the geometry. Raw
OpenROAD violation records avoid rounded ratios and wrapped table names.
"""
import hashlib,json,pathlib
import odb
from decimal import Decimal
from reader import click_odb,click
from diodes import DiodeInserter

def violations(text):
    """Read raw OpenROAD records, never Rich's rounded/wrapped summary.

    VIOLATED is authoritative: displayed ratios may round to equality.
    Every marked record must have complete, finite numeric context.
    """
    import re
    number=r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)'
    patterns={key:re.compile(r'^\s*'+label+r':\s*'+value)
              for key,label,value in [('net','Net',r'(\S+)'),('pin','Pin',r'(\S+)'),
                                      ('layer','Layer',r'(\S+)'),
                                      ('required','Required ratio',number),
                                      ('partial','Partial area ratio',number)]}
    record={};pins=[]
    for line in text.splitlines():
        for key,pattern in patterns.items():
            match=pattern.match(line)
            if match:
                if key=='net':record={}
                elif key=='pin':record={k:v for k,v in record.items() if k=='net'}
                elif key=='layer':record={k:v for k,v in record.items() if k in ('net','pin')}
                record[key]=match.group(1)
        if 'VIOLATED' not in line:continue
        if set(record)!=set(patterns):raise ValueError('Incomplete raw antenna violation: '+line)
        required=Decimal(record['required']);partial=Decimal(record['partial'])
        if not required.is_finite() or not partial.is_finite() or required<=0 or partial<0:
            raise ValueError('Invalid raw antenna ratio: '+line)
        if '/' not in record['pin']:raise ValueError('Raw antenna violation has no instance/pin: '+record['pin'])
        pins.append((record['net'],record['pin']))
    return sorted(set(pins))

def rectangle(inst):
    r=inst.getBBox();return (r.xMin(),r.yMin(),r.xMax(),r.yMax())

def overlaps(a,b):return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]

def fix_adjacent_pair(block,gate,diode):
    """Keep the diode local without fixing it on top of an immovable tap.

    Movable neighbors are left to the normal legalizer. Try the opposite side
    first; only then shift the pair by whole placement sites on the same row.
    """
    gx,gy=gate.getLocation();dx,dy=diode.getLocation()
    gr=rectangle(gate);dr=rectangle(diode);gw=gr[2]-gr[0];dw=dr[2]-dr[0]
    site=gate.getMaster().getSite().getWidth()
    fixed=[rectangle(i) for i in block.getInsts()
           if i.getName() not in (gate.getName(),diode.getName())
           and i.getPlacementStatus() in ('FIRM','LOCKED')
           and rectangle(i)[1]<gr[3] and gr[1]<rectangle(i)[3]]
    bounds=[row.getBBox() for row in block.getRows() if row.getBBox().yMin()==gr[1]]
    if not bounds:raise ValueError('No placement row for protected gate '+gate.getName())
    xmin=min(r.xMin() for r in bounds);xmax=max(r.xMax() for r in bounds)
    sides=('left','right') if dx<gx else ('right','left')
    shifts=[0]
    if gate.getPlacementStatus() not in ('FIRM','LOCKED'):
        shifts += [direction*n*site for n in range(1,51) for direction in (-1,1)]
    for shift in shifts:
        gate_box=(gr[0]+shift,gr[1],gr[2]+shift,gr[3])
        if gate_box[0]<xmin or gate_box[2]>xmax or any(overlaps(gate_box,b) for b in fixed):continue
        for offset in range(32):
            for side in sides:
                x=gate_box[0]-dw*(offset+1) if side=='left' else gate_box[2]+dw*offset
                box=(x,dr[1],x+dw,dr[3])
                if x<xmin or x+dw>xmax or any(overlaps(box,b) for b in fixed):continue
                gate.setLocation(gx+shift,gy);diode.setLocation(x,dy)
                gate.setPlacementStatus('FIRM');diode.setPlacementStatus('FIRM')
                return {'gate':gate.getName(),'gate_shift_dbu':shift,'diode':diode.getName(),'diode_x_dbu':x}
    raise ValueError('No legal adjacent site for '+gate.getName())

@click.command()
@click.option('--report',required=True,type=click.Path(exists=True))
@click.option('--evidence',required=True,type=click.Path())
@click.option('--diode-cell',default='sky130_fd_sc_hd__diode_2')
@click.option('--diode-pin',default='DIODE')
@click.option('--fix-pairs',is_flag=True,help='Keep the protected gate/diode adjacent during legalization')
@click.option('--clear-routing',is_flag=True,help='Remove obsolete signal wires before re-routing the changed layout')
@click_odb
def protect(reader,report,evidence,diode_cell,diode_pin,fix_pairs,clear_routing):
    path=pathlib.Path(report);pins=violations(path.read_text())
    if not pins:raise ValueError('Active antenna ECO has no complete raw VIOLATED records')
    inserter=DiodeInserter(reader,diode_cell,diode_pin,Decimal(0),side_strategy='pin');placement=[]
    for net_name,pin in pins:
        inst_name,pin_name=pin.rsplit('/',1)
        inst=reader.block.findInst(inst_name)
        if inst is None:raise ValueError('Reported instance absent from checkpoint: '+pin)
        term=inst.findITerm(pin_name)
        def canonical(name):return name.replace('\\[','[').replace('\\]',']')
        if term is None or term.getNet() is None or canonical(term.getNet().getName())!=canonical(net_name):
            raise ValueError('Reported pin/net does not match checkpoint: '+pin)
        before={t.getInst().getName() for t in term.getNet().getITerms()}
        inserter.insert_diode(term.getNet(),term,inserter.net_source(term.getNet()))
        if fix_pairs:
            added=[t.getInst() for t in term.getNet().getITerms() if t.getInst().getName() not in before]
            if len(added)!=1:raise ValueError('Expected one new diode for '+pin)
            placement.append(fix_adjacent_pair(reader.block,inst,added[0]))
    removed=0
    if clear_routing:
        for net in reader.block.getNets():
            if net.getSigType() not in ('POWER','GROUND') and net.getWire() is not None:
                odb.dbWire_destroy(net.getWire());removed+=1
    pathlib.Path(evidence).write_text(json.dumps({'action':'insert_local_diodes','pins':pins,'placement':placement,'removed_signal_routes':removed,
        'count':len(pins),'fixed_pairs':fix_pairs,'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'status':'requires_legalization_routing_and_independent_checks'},indent=2)+'\n')

if __name__=='__main__':protect()
