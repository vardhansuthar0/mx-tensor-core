"""pyuvm components + cocotb BFM; coverage samples verified retired blocks."""
import json, os, random
from collections import deque
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
import pyuvm
from cocotb_coverage.coverage import CoverPoint, coverage_db
from model.mx import dot
from tb.cases import Block, cases, SCENARIOS, scenario_hits, rounding_class

BINS=[(f,b,t,s) for f in range(5) for b in (False,True) for t in (0,1) for s in SCENARIOS]
@CoverPoint('mx.contract',xf=lambda x:x,bins=BINS)
def sample_contract(key):
    pass

class Scoreboard(pyuvm.uvm_scoreboard):
    def build_phase(self):
        self.expected=deque();self.checked=0;self.aborted=0;self.stalls=0;self.resets=0
        self.accepted=0;self.seen=set();self.specials=set();self.partial_a=[];self.partial_b=[]
        self.config=None;self.block_start=0;self.cycle=0;self.previous_stall=None
        self.pending_tags=deque();self.rounding=set();self.retire_cycles=[]
    def observe(self,d,rst,lanes,stages):
        self.cycle+=1
        if rst:
            self.aborted+=len(self.expected);self.expected.clear();self.partial_a=[];self.partial_b=[]
            self.previous_stall=None;self.resets+=1
            return
        if self.previous_stall is not None:
            assert int(d.out_valid.value), 'PROTOCOL: valid dropped under stall'
            assert (int(d.out_data.value),int(d.out_flags.value))==self.previous_stall, 'PROTOCOL: stalled payload changed'
        if int(d.out_valid.value):
            assert self.expected, 'SCOREBOARD: unsolicited/duplicate output'
            data,flags,block,earliest=self.expected[0]
            assert self.cycle>=earliest, 'PROTOCOL: output arrived before specified latency'
            if int(d.out_ready.value):
                self.expected.popleft()
                got=(int(d.out_data.value),int(d.out_flags.value))
                assert got==(data,flags), f'SCOREBOARD: {block} expected {data:08x}/{flags:02x}, got {got[0]:08x}/{got[1]:02x}'
                self.checked+=1;self.retire_cycles.append(self.cycle)
                for scenario in scenario_hits(block):
                    key=(block.fmt,block.bf16,block.trunc,scenario)
                    if key in BINS: self.seen.add(key);sample_contract(key)
                rc=rounding_class(block)
                if rc: self.rounding.add(rc)
                self.specials.add(block.tag)
        self.previous_stall=((int(d.out_data.value),int(d.out_flags.value))
                             if int(d.out_valid.value) and not int(d.out_ready.value) else None)
        if self.previous_stall: self.stalls+=1
        if int(d.in_valid.value) and int(d.in_ready.value):
            if not self.partial_a:
                self.config=(int(d.in_fmt.value),int(d.in_scale_a.value),int(d.in_scale_b.value),
                             bool(int(d.in_bf16.value)),int(d.in_trunc.value))
                self.block_start=self.cycle
            av,bv=int(d.in_a.value),int(d.in_b.value)
            self.partial_a.extend((av>>(8*i))&255 for i in range(lanes))
            self.partial_b.extend((bv>>(8*i))&255 for i in range(lanes))
            if len(self.partial_a)==32:
                tag=self.pending_tags.popleft()
                block=Block(self.partial_a,self.partial_b,*self.config,tag=tag)
                data,flags=dot(block.a,block.b,block.fmt,block.sa,block.sb,block.bf16,block.trunc)
                self.expected.append((data,flags,block,self.cycle+stages))
                self.accepted+=1;self.partial_a=[];self.partial_b=[]

class Agent(pyuvm.uvm_agent):
    def build_phase(self):
        self.rng=random.Random(7331)
    async def tick(self,rst=False):
        d=self.dut;d.clk.value=0;d.rst.value=int(rst)
        await Timer(5,unit='ns')
        self.scoreboard.observe(d,rst,self.lanes,self.stages)
        accepted=bool(int(d.in_valid.value) and int(d.in_ready.value) and not rst)
        d.clk.value=1
        await Timer(5,unit='ns')
        return accepted
    async def reset(self):
        self.dut.in_valid.value=0;self.dut.out_ready.value=0
        await self.tick(True);await self.tick(True)
        self.scoreboard.pending_tags.clear()
    async def execute(self,blocks,drain=True,stress=True):
        d=self.dut
        for block in blocks:
            self.scoreboard.pending_tags.append(block.tag)
            for start in range(0,32,self.lanes):
                d.in_valid.value=0
                for _ in range(self.rng.randrange(3) if stress else 0):
                    d.out_ready.value=int(self.rng.random()>.3);await self.tick()
                d.in_valid.value=1
                d.in_a.value=sum(x<<(8*i) for i,x in enumerate(block.a[start:start+self.lanes]))
                d.in_b.value=sum(x<<(8*i) for i,x in enumerate(block.b[start:start+self.lanes]))
                # Deliberately alter non-first sidebands to verify snapshots.
                d.in_fmt.value=block.fmt if start==0 else self.rng.randrange(8)
                d.in_scale_a.value=block.sa if start==0 else self.rng.randrange(256)
                d.in_scale_b.value=block.sb if start==0 else self.rng.randrange(256)
                d.in_bf16.value=block.bf16 if start==0 else self.rng.randrange(2)
                d.in_trunc.value=block.trunc if start==0 else self.rng.randrange(32)
                for attempt in range(1000):
                    d.out_ready.value=int(not stress or self.rng.random()>.35)
                    if await self.tick(): break
                else: raise AssertionError('PROTOCOL: input deadlock')
        d.in_valid.value=0
        if drain:
            d.out_ready.value=1
            for _ in range(100):
                await self.tick()
                if not self.scoreboard.expected: break
            assert not self.scoreboard.expected, 'PROTOCOL: dropped transaction/deadlock'
            for _ in range(8): await self.tick()

class Environment(pyuvm.uvm_env):
    def build_phase(self):
        self.agent=Agent('agent',self);self.sb=Scoreboard('scoreboard',self)
    def connect_phase(self):
        self.agent.scoreboard=self.sb;self.agent.dut=cocotb.top
        self.agent.lanes=int(os.environ['MX_LANES']);self.agent.stages=int(os.environ['MX_STAGES'])

@pyuvm.test()
class Regression(pyuvm.uvm_test):
    def build_phase(self):
        self.env=Environment('env',self)
    async def run_phase(self):
        self.raise_objection()
        a=self.env.agent;d=a.dut
        d.in_a.value=0;d.in_b.value=0;d.in_fmt.value=0;d.in_scale_a.value=127;d.in_scale_b.value=127
        d.in_trunc.value=0;d.in_bf16.value=0
        await a.reset()
        # Flush occupied pipeline. Also abort a partial block in narrow modes.
        await a.execute(cases(count=0)[:3],drain=False)
        await a.reset()
        if a.lanes<32:
            d.in_valid.value=1;d.out_ready.value=1;d.in_a.value=1;d.in_b.value=1
            await a.tick();await a.reset()
        await a.execute([Block([0x38]*32,[0x38]*32,tag='throughput') for _ in range(64)],stress=False)
        cycles=self.env.sb.retire_cycles[-64:]
        assert len(cycles)==64 and all(y-x==32//a.lanes for x,y in zip(cycles,cycles[1:])), 'PROTOCOL: sustained throughput'
        await a.execute(cases(count=int(os.environ['MX_COUNT'])))
        sb=self.env.sb
        missing=set(BINS)-sb.seen
        assert not missing, f'COVERAGE: missing contract bins {missing}'
        assert sb.stalls>0, 'COVERAGE: no backpressure exercised'
        rounding_bins={'exact','below_half','tie_even','tie_odd','above_half','overflow','underflow'}
        assert sb.rounding==rounding_bins, f'COVERAGE: rounding bins {rounding_bins-sb.rounding}'
        report={'status':'pass','lanes':a.lanes,'pipeline_stages':a.stages,
                'checked_blocks':sb.checked,'accepted_blocks':sb.accepted,'aborted_blocks':sb.aborted,
                'stalled_cycles':sb.stalls,'reset_cycles':sb.resets,
                'functional_coverage':{'name':'format x output x exact/trunc1 x 8 directed scenarios',
                                       'hit':len(sb.seen),'total':len(BINS),'percent':100*len(sb.seen)/len(BINS)},
                'rounding_bins':sorted(sb.rounding),
                'scope':'160 contract bins plus seven rounding classes; not complete arithmetic or code coverage.',
                'sustained_cycles_per_block':32//a.lanes,'throughput_test_blocks':64,'seed':20261011}
        Path(os.environ['MX_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
        coverage_db.export_to_yaml(str(Path(os.environ['MX_REPORT']).with_suffix('.coverage.yml')))
        self.drop_objection()
