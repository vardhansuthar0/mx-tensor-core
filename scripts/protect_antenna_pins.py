"""Place a local diode beside each pin in an actual antenna violation report.

This changes the layout; it does not waive any antenna or electrical check.
The following legalization, routing, extraction and independent checks remain
necessary. OpenLane's pin-side diode placement utility supplies the geometry.
"""
import hashlib,json,pathlib
import odb
from decimal import Decimal
from reader import click_odb,click
from diodes import DiodeInserter

def violations(text):
    if not all(label in text for label in ('P / R','Required','Net','Pin','Layer')):
        raise ValueError('Not an OpenLane antenna summary')
    pins=[]
    for line in text.splitlines():
        if not line.startswith('│'):continue
        fields=[x.strip() for x in line.split('│')[1:-1]]
        if len(fields)!=6:raise ValueError('Malformed antenna report row')
        ratio,partial,required,net,pin,layer=fields
        if float(ratio)<=1 or float(partial)<=float(required):raise ValueError('Non-violating row in antenna report')
        pins.append((net,pin))
    return sorted(set(pins))

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
    inserter=DiodeInserter(reader,diode_cell,diode_pin,Decimal(0),side_strategy='pin')
    for net_name,pin in pins:
        inst_name,pin_name=pin.rsplit('/',1)
        inst=reader.block.findInst(inst_name)
        if inst is None:raise ValueError('Reported instance absent from checkpoint: '+pin)
        term=inst.findITerm(pin_name)
        if term is None or term.getNet() is None or term.getNet().getName()!=net_name:
            raise ValueError('Reported pin/net does not match checkpoint: '+pin)
        before={t.getInst().getName() for t in term.getNet().getITerms()}
        inserter.insert_diode(term.getNet(),term,inserter.net_source(term.getNet()))
        if fix_pairs:
            added=[t.getInst() for t in term.getNet().getITerms() if t.getInst().getName() not in before]
            if len(added)!=1:raise ValueError('Expected one new diode for '+pin)
            inst.setPlacementStatus('FIRM');added[0].setPlacementStatus('FIRM')
    removed=0
    if clear_routing:
        for net in reader.block.getNets():
            if net.getSigType() not in ('POWER','GROUND') and net.getWire() is not None:
                odb.dbWire_destroy(net.getWire());removed+=1
    pathlib.Path(evidence).write_text(json.dumps({'action':'insert_local_diodes','pins':pins,'removed_signal_routes':removed,
        'count':len(pins),'fixed_pairs':fix_pairs,'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'status':'requires_legalization_routing_and_independent_checks'},indent=2)+'\n')

if __name__=='__main__':protect()
