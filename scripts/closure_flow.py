"""Repeat antenna repair after legalization/re-routing can create new violations.
All independent antenna checks and downstream signoff checkers are retained.
"""
from openlane.flows import Flow
from openlane.flows.classic import Classic
from openlane.steps import OpenROAD,OdbpyStep
from openlane.config import Variable
from openlane.state import DesignFormat
from typing import List
import pathlib

class RepairSlowCorner(OpenROAD.RepairDesignPostGRT):
    """Optimize electrical limits using the slow library as the sole corner.

    The final STA still checks every original corner. This avoids treating
    a typical-corner electrical repair as sufficient for slow-corner slew.
    """
    id="MX.RepairSlowCorner"
    config_vars=OpenROAD.RepairDesignPostGRT.config_vars+[
        Variable("CLOSURE_REPAIR_CORNERS",List[str],
                 "Corners used by the extra electrical repair only; final STA unchanged.",
                 default=["max_ss_100C_1v60"])]
    def run(self,state_in,**kwargs):
        return super().run(state_in,corners_key="CLOSURE_REPAIR_CORNERS",**kwargs)

class RepairClockElectrical(RepairSlowCorner):
    id="MX.RepairClockElectrical"
    def get_script_path(self):return str(pathlib.Path(__file__).with_name('repair_clocks.tcl'))

class ProtectAntennaPins(OdbpyStep):
    id="MX.ProtectAntennaPins"
    def get_script_path(self):return str(pathlib.Path(__file__).with_name('protect_antenna_pins.py'))
    def get_command(self):
        root=pathlib.Path(self.step_dir).parent
        reports=list(root.rglob('antenna_summary.rpt'))
        if not reports:
            odb=pathlib.Path(str(self.state_in.result()[DesignFormat.ODB]))
            for parent in odb.parents:
                if parent.name=='runs':break
                reports=list(parent.rglob('antenna_summary.rpt'))
                if reports:break
        if not reports:raise RuntimeError('No measured antenna report for local pin protection')
        report=max(reports,key=lambda p:p.stat().st_mtime_ns)
        return super().get_command()+['--report',str(report),'--evidence',str(pathlib.Path(self.step_dir)/'local-diodes.json'),'--fix-pairs','--clear-routing']
    def run(self,state_in,**kwargs):
        active=state_in.metrics.get('antenna__violating__pins',0)>0
        if not active:return {},{'mx__antenna_eco_active':0}
        views,metrics=super().run(state_in,**kwargs)
        metrics['mx__antenna_eco_active']=1
        return views,metrics

class ConditionalAntennaECO:
    def run(self,state_in,**kwargs):
        if not state_in.metrics.get('mx__antenna_eco_active',0):return {},{}
        return super().run(state_in,**kwargs)

class ECOLegalize(ConditionalAntennaECO,OpenROAD.DetailedPlacement):id="MX.ECOLegalize"
class ECOGlobalRoute(ConditionalAntennaECO,OpenROAD.GlobalRouting):id="MX.ECOGlobalRoute"
class ECODetailedRoute(ConditionalAntennaECO,OpenROAD.DetailedRouting):id="MX.ECODetailedRoute"
class ECOCheckAntennas(ConditionalAntennaECO,OpenROAD.CheckAntennas):id="MX.ECOCheckAntennas"

@Flow.factory.register()
class MXClosure(Classic):
    Steps=[]
    for step in Classic.Steps:
        Steps.append(step)
        if step is OpenROAD.RepairAntennas:
            Steps.extend([OpenROAD.RepairDesignPostGRT,OpenROAD.RepairAntennas]*3)
        if step is OpenROAD.ResizerTimingPostGRT:
            # Placement and re-routing can reintroduce violations, so repair
            # repeatedly. Antenna repair runs after the last buffer changes.
            Steps.extend([RepairSlowCorner]*3+[OpenROAD.RepairAntennas,RepairSlowCorner,RepairClockElectrical,OpenROAD.ResizerTimingPostCTS,OpenROAD.GlobalRouting])
        if step.id=="OpenROAD.CheckAntennas-1":
            # Protect pins measured on detailed wires, then re-route and check
            # again. Clean rounds skip all geometry changes and router work.
            Steps.extend([ProtectAntennaPins,ECOLegalize,ECOGlobalRoute,ECODetailedRoute,ECOCheckAntennas]*3)
