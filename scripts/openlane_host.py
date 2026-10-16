"""Hosted OpenLane compatibility. Checker logic and exit statuses stay active."""
import os

def configure():
    from openlane.steps.step import DefaultOutputProcessor, ProcessStatsThread
    if os.environ.get('MX_DISABLE_PROCESS_STATS')=='1':
        def wait_for_child(self):
            self.process.wait()
        ProcessStatsThread.run=wait_for_child
    # A subsequent STA annotation checker reads these files immediately. Flush
    # each emitted report line so it cannot observe a buffered/truncated tail.
    original=DefaultOutputProcessor.process_line
    def flush_reports(self,line):
        result=original(self,line)
        if self.current_rpt is not None:self.current_rpt.flush()
        return result
    DefaultOutputProcessor.process_line=flush_reports

if __name__=='__main__':
    configure()
    import closure_flow  # register MXClosure without changing checker behavior
    from openlane.__main__ import cli
    cli()
