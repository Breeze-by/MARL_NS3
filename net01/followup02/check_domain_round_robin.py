"""Exact Gateway AST with controlled public executors; no ROS/Node or I/O."""
import ast,json,time
from collections import deque
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[1];tree=ast.parse((root/'gateway.py').read_text())
f=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='drain_current_ready')
c=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Gateway');poll=next(x for x in c.body if isinstance(x,ast.FunctionDef) and x.name=='poll')
class TimeoutException(Exception):pass
class ShutdownException(Exception):pass
ns=dict(time=time,TimeoutException=TimeoutException,ShutdownException=ShutdownException)
exec(compile(ast.Module(body=[f,poll],type_ignores=[]),'actual_gateway_methods','exec'),ns)
checks={};order=[]
class Node:
    def __init__(self,cap):self.subscriptions=tuple(range(cap));self.timers=self.clients=self.services=self.guards=self.waitables=()
class Handler:
    def __init__(self,name,callback=None,error=None):self.name=name;self.callback=callback;self.error=error
    def __call__(self):
        order.append(self.name)
        if self.callback:self.callback()
    def exception(self):return self.error
    def result(self):return None
class Executor:
    def __init__(self,events):self.events=deque(events);self.calls=0
    def wait_for_ready_callbacks(self,timeout_sec):
        assert timeout_sec==0;self.calls+=1;x=self.events.popleft() if self.events else TimeoutException()
        if isinstance(x,BaseException):raise x
        return x,x,None

def subject(C,R,capC=2,capR=2):
    stat=lambda:dict(batches=0,callbacks=0,cap_hits=0,max_wall_s=0.,max_cpu_s=0.)
    s=SimpleNamespace(last_poll=None,nodes=[Node(capC),Node(capR)],executors=[C,R],ready_sets={k:dict(productive=False) for k in ('C','R')},dispatch_stats=dict(C=stat(),R=stat(),guard_timers={},max_poll_gap_wall_s=0.),guards={})
    s.pumps=0
    def pump():s.pumps+=1
    s.progress_transport=pump
    return s
C=Executor([Handler('C1'),TimeoutException(),Handler('C2'),TimeoutException(),Handler('C3')]);R=Executor([Handler('R1'),TimeoutException(),Handler('R2'),TimeoutException(),Handler('R3')]);s=subject(C,R);ns['poll'](s)
checks['both_busy_alternate_in_original_side_order']=order==['C1','R1','C2','R2']
checks['handler_pump_and_empty_tail_preserved']=s.pumps==5
ns['poll'](s);checks['cap_cursor_and_productive_tail_resume']=order==['C1','R1','C2','R2','C3','R3']
checks['original_real_callback_counts']=s.dispatch_stats['C']['callbacks']==3 and s.dispatch_stats['R']['callbacks']==3
order.clear();C=Executor([]);R=Executor([Handler('Rproduce',lambda:C.events.append(Handler('Cnew'))),Handler('R2')]);s=subject(C,R);ns['poll'](s)
checks['empty_C_is_reprobed_after_R_produces_C']=order==['Rproduce','Cnew','R2']
order.clear();C=Executor([Handler('C1'),Handler('C2')]);R=Executor([Handler('R1'),Handler('R2'),Handler('R3'),Handler('R4')]);s=subject(C,R,1,4);ns['poll'](s)
checks['short_C_cap_ends_pair_without_R_tail_monopoly']=order==['C1','R1']
ns['poll'](s);checks['unused_R_budget_is_deferred_not_added']=order==['C1','R1','C2','R2']
order.clear();C=Executor([ShutdownException()]);R=Executor([Handler('R1'),Handler('R2')]);s=subject(C,R);ns['poll'](s)
checks['shutdown_stops_only_that_side_this_poll']=C.calls==1 and order==['R1','R2']
C=Executor([]);R=Executor([]);s=subject(C,R);ns['poll'](s);checks['both_empty_return_without_busy_retry']=C.calls==R.calls==1 and s.pumps==1
order.clear();error=ValueError('original handler');s=subject(Executor([Handler('Cerror',error=error)]),Executor([Handler('RmustNotRun')]))
try:ns['poll'](s)
except ValueError as e:checks['handler_exception_propagates_before_other_side']=e is error and order==['Cerror']
order.clear();s=subject(Executor([]),Executor([]),1,4);s.executors[0].events.append(Handler('Cgrow',lambda:setattr(s.nodes[0],'subscriptions',tuple(range(30)))));s.executors[1].events.extend([Handler('R1'),Handler('R2')]);ns['poll'](s)
checks['caps_fixed_once_at_poll_entry']=order==['Cgrow','R1']
order.clear();h=Handler('Rtimer');s=subject(Executor([]),Executor([h]));s.guards={1:SimpleNamespace(timer=h)};ns['poll'](s)
checks['guard_stats_keep_actual_handler_begin']=s.dispatch_stats['guard_timers']['1']['calls']==1 and s.dispatch_stats['guard_timers']['1']['last']>0
result=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,scope='Actual Gateway poll/drain AST, controlled public executor interface; no Node/ROS/GZ/NN/transport test',calls=dict(Node=0,Gazebo=0,NN=0))
Path(__file__).with_name('DOMAIN_ROUND_ROBIN_CHECK.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0 if all(checks.values()) else 1)
