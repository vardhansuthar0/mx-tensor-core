"""Run OpenLane on hosts where psutil sees a different /proc PID namespace.
Only optional CPU/RSS telemetry is disabled. Tool exit codes and every design
checker remain active. Resource statistics in this mode must not be reported.
"""
import os
if os.environ.get('MX_DISABLE_PROCESS_STATS')=='1':
    from openlane.steps.step import ProcessStatsThread
    def wait_for_child(self):
        self.process.wait()
    ProcessStatsThread.run=wait_for_child
from openlane.__main__ import cli
cli()
