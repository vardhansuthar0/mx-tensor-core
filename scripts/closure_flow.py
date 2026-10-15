"""Repeat antenna repair after legalization/re-routing can create new violations.
All independent antenna checks and downstream signoff checkers are retained.
"""
from openlane.flows import Flow
from openlane.flows.classic import Classic
from openlane.steps import OpenROAD

@Flow.factory.register()
class MXClosure(Classic):
    Steps=[]
    for step in Classic.Steps:
        Steps.append(step)
        if step is OpenROAD.RepairAntennas:
            Steps.extend([OpenROAD.RepairDesignPostGRT,OpenROAD.RepairAntennas]*3)
