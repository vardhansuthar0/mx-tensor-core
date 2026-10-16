"""Regression tests for raw antenna records and local fixed-cell geometry."""
import ast
from decimal import Decimal
from pathlib import Path
import pytest
SOURCE=Path(__file__).parents[1]/'scripts/protect_antenna_pins.py'
# Load the real pure functions without importing OpenROAD's embedded Python.
tree=ast.parse(SOURCE.read_text())
names={'violations','rectangle','overlaps','fix_adjacent_pair'}
functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
assert {node.name for node in functions}==names
namespace={'Decimal':Decimal}
exec(compile(ast.Module(body=functions,type_ignores=[]),str(SOURCE),'exec'),namespace)
violations=namespace['violations'];fix_pair=namespace['fix_adjacent_pair'];overlaps=namespace['overlaps'];rectangle=namespace['rectangle']

def record(net='core.products[223]',pin='_123_/A',partial='400.00',required='400.00',layer='met2'):
    return f'Net: {net}\n  Pin: {pin}\n    Layer: {layer}\n      Partial area ratio: {partial}\n      Required ratio: {required}\n      VIOLATED\n'

def test_raw_marker_survives_display_rounding():
    assert violations(record())==[('core.products[223]','_123_/A')]

def test_long_raw_names_are_not_wrapped_or_rich_escaped():
    net='core.'+'long_array_path_'*20+'products[223]'
    pin='core.'+'long_instance_path_'*20+'gate/A'
    assert violations(record(net,pin))==[(net,pin)]

def test_all_marked_layers_and_pins_are_consumed():
    text=record()+record(layer='met3')+record('other[7]','gate/B',partial='8.0e2',required='4e2')
    assert violations(text)==[('core.products[223]','_123_/A'),('other[7]','gate/B')]

@pytest.mark.parametrize('bad',[
    'Net: net1\n Pin: gate/A\n VIOLATED\n',
    record()+ 'Net: net2\n Pin: gate/B\n Layer: met3\n VIOLATED\n',
    record(required='0'),
    record(pin='missing_instance_separator')])
def test_incomplete_or_invalid_raw_records_fail_closed(bad):
    with pytest.raises(ValueError):violations(bad)

def test_unmarked_records_do_not_create_repairs():
    assert violations(record().replace('VIOLATED',''))==[]

class Box:
    def __init__(self,x,y,w,h):self.coords=(x,y,x+w,y+h)
    def xMin(self):return self.coords[0]
    def yMin(self):return self.coords[1]
    def xMax(self):return self.coords[2]
    def yMax(self):return self.coords[3]
class Site:
    def getWidth(self):return 1
class Master:
    def getSite(self):return Site()
class Inst:
    def __init__(self,name,x,w,status='PLACED',y=0):
        self.name=name;self.x=x;self.y=y;self.w=w;self.status=status
    def getBBox(self):return Box(self.x,self.y,self.w,2)
    def getLocation(self):return self.x,self.y
    def setLocation(self,x,y):self.x=x;self.y=y
    def getMaster(self):return Master()
    def getName(self):return self.name
    def getPlacementStatus(self):return self.status
    def setPlacementStatus(self,status):self.status=status
class Row:
    def __init__(self,width):self.width=width
    def getBBox(self):return Box(0,0,self.width,2)
class Block:
    def __init__(self,instances,width=100):self.instances=instances;self.width=width
    def getInsts(self):return self.instances
    def getRows(self):return [Row(self.width)]

def assert_legal(block,gate,diode):
    for inst in (gate,diode):
        box=rectangle(inst)
        assert 0<=box[0] and box[2]<=block.width and inst.status=='FIRM'
        for other in block.instances:
            if other is inst or other is gate or other is diode:continue
            if other.status in ('FIRM','LOCKED'):assert not overlaps(box,rectangle(other))
    assert not overlaps(rectangle(gate),rectangle(diode))

def test_opposite_side_avoids_fixed_tap():
    gate=Inst('gate',10,4);diode=Inst('diode',8,2);tap=Inst('tap',8,2,'FIRM')
    block=Block([gate,diode,tap]);fix_pair(block,gate,diode)
    assert gate.x==10 and diode.x==14;assert_legal(block,gate,diode)

def test_later_eco_can_place_beyond_four_occupied_slots():
    gate=Inst('gate',40,4,'FIRM');diode=Inst('new_diode',38,2)
    occupied=[Inst('existing'+str(i),x,2,'FIRM') for i,x in enumerate([38,36,34,32,44,46,48,50])]
    block=Block([gate,diode]+occupied);fix_pair(block,gate,diode)
    assert gate.x==40 and diode.x==30;assert_legal(block,gate,diode)

def test_movable_neighbor_gate_rehomes_away_from_earlier_fixed_diode():
    gate=Inst('gate',10,4);diode=Inst('new',8,2);earlier=Inst('earlier',12,2,'FIRM')
    block=Block([gate,diode,earlier]);result=fix_pair(block,gate,diode)
    assert result['gate_shift_dbu']==-2;assert_legal(block,gate,diode)

def test_boundary_keeps_diode_inside_row():
    gate=Inst('gate',0,4);diode=Inst('diode',-2,2)
    block=Block([gate,diode]);fix_pair(block,gate,diode)
    assert diode.x==4;assert_legal(block,gate,diode)

def test_no_legal_site_fails_without_moving_fixed_gate():
    gate=Inst('gate',4,4,'FIRM');diode=Inst('diode',2,2)
    block=Block([gate,diode,Inst('left',0,4,'FIRM'),Inst('right',8,4,'FIRM')],12)
    with pytest.raises(ValueError,match='No legal adjacent site'):fix_pair(block,gate,diode)
    assert gate.x==4

def test_native_inline_markers_and_cumulative_records():
    text="""Net: net1
  Pin: gate/A (sky130_fd_sc_hd__and2_1)
    Layer: met3
      Partial area ratio: 400.00
      Required ratio: 400.00 (Gate area) (VIOLATED)
      Cumulative area ratio: 500.00
      Required ratio: 500.00 (Cumulative area) (VIOLATED)
"""
    assert violations(text)==[('net1','gate/A')]
