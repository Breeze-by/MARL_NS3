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
C=Executor([value for i in range(1,6) for value in (Handler('C'+str(i)),TimeoutException())]);R=Executor([value for i in range(1,6) for value in (Handler('R'+str(i)),TimeoutException())]);s=subject(C,R,4,4);ns['poll'](s)
checks['both_busy_fixed_four_preserves_side_order']=order==['C1','C2','C3','C4','R1','R2','R3','R4']
checks['handler_pump_and_empty_tail_preserved']=s.pumps==9
ns['poll'](s);checks['cap_cursor_and_productive_tail_resume']=order==['C1','C2','C3','C4','R1','R2','R3','R4','C5','R5']
checks['original_real_callback_counts']=s.dispatch_stats['C']['callbacks']==5 and s.dispatch_stats['R']['callbacks']==5
order.clear();C=Executor([]);R=Executor([Handler('Rproduce',lambda:C.events.append(Handler('Cnew')))]+[Handler('R'+str(i)) for i in range(2,9)]);s=subject(C,R,2,8);ns['poll'](s)
checks['empty_C_reprobed_after_at_most_four_R']=order==['Rproduce','R2','R3','R4','Cnew','R5','R6','R7','R8']
order.clear();C=Executor([Handler('C1'),Handler('C2')]);R=Executor([Handler('R'+str(i)) for i in range(1,9)]);s=subject(C,R,1,10);ns['poll'](s)
checks['short_C_cap_ends_pair_without_R_tail_monopoly']=order==['C1','R1','R2','R3','R4']
ns['poll'](s);checks['unused_R_budget_is_deferred_not_added']=order==['C1','R1','R2','R3','R4','C2','R5','R6','R7','R8']
order.clear();s=subject(Executor([Handler('C'+str(i)) for i in range(1,9)]),Executor([Handler('R'+str(i)) for i in range(1,13)]),6,10);ns['poll'](s)
checks['last_pair_respects_each_remaining_cap']=s.dispatch_stats['C']['callbacks']==6 and s.dispatch_stats['R']['callbacks']==8 and order==['C1','C2','C3','C4','R1','R2','R3','R4','C5','C6','R5','R6','R7','R8']
order.clear();C=Executor([ShutdownException()]);R=Executor([Handler('R1'),Handler('R2')]);s=subject(C,R);ns['poll'](s)
checks['shutdown_stops_only_that_side_this_poll']=C.calls==1 and order==['R1','R2']
C=Executor([]);R=Executor([]);s=subject(C,R);ns['poll'](s);checks['both_empty_return_without_busy_retry']=C.calls==R.calls==1 and s.pumps==1
order.clear();error=ValueError('original handler');s=subject(Executor([Handler('Cerror',error=error)]),Executor([Handler('RmustNotRun')]))
try:ns['poll'](s)
except ValueError as e:checks['handler_exception_propagates_before_other_side']=e is error and order==['Cerror']
order.clear();s=subject(Executor([]),Executor([]),1,4);s.executors[0].events.append(Handler('Cgrow',lambda:setattr(s.nodes[0],'subscriptions',tuple(range(30)))));s.executors[1].events.extend([Handler('R'+str(i)) for i in range(1,6)]);ns['poll'](s)
checks['caps_fixed_once_at_poll_entry']=order==['Cgrow','R1','R2','R3','R4']
order.clear();h=Handler('Rtimer');s=subject(Executor([]),Executor([h]));s.guards={1:SimpleNamespace(timer=h)};ns['poll'](s)
checks['guard_stats_keep_actual_handler_begin']=s.dispatch_stats['guard_timers']['1']['calls']==1 and s.dispatch_stats['guard_timers']['1']['last']>0
result=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,scope='Actual Gateway poll/drain AST, controlled public executor interface; no Node/ROS/GZ/NN/transport test',calls=dict(Node=0,Gazebo=0,NN=0))
Path(__file__).with_name('DOMAIN_QUANTUM4_CHECK.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0 if all(checks.values()) else 1)
