"""No-Node controlled executor checks of the exact Gateway function AST."""
import ast,json,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
tree=ast.parse((root/'gateway.py').read_text());function=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='drain_current_ready')
class TimeoutException(Exception):pass
class ShutdownException(Exception):pass
ns=dict(time=time,TimeoutException=TimeoutException,ShutdownException=ShutdownException)
exec(compile(ast.Module(body=[function],type_ignores=[]),'actual_gateway_function','exec'),ns)
drain=ns['drain_current_ready'];checks={};order=[]
class Node:
    subscriptions=(1,2);timers=clients=services=guards=waitables=()
class Handler:
    def __init__(self,name,error=None):self.name=name;self.error=error;self.results=0
    def __call__(self):order.append(self.name)
    def exception(self):return self.error
    def result(self):self.results+=1
class Executor:
    def __init__(self,events):self.events=iter(events);self.calls=0
    def wait_for_ready_callbacks(self,timeout_sec):
        assert timeout_sec==0;self.calls+=1;event=next(self.events)
        if isinstance(event,BaseException):raise event
        return event,event.name,None
empty=Executor([TimeoutException()]);state=dict(productive=False)
a,cap=drain(empty,Node(),state);checks['empty_set_returns_one_attempt']=not a and empty.calls==1 and cap==2
h1,h2,h3=[Handler(str(i)) for i in (1,2,3)]
e=Executor([h1,h2,TimeoutException(),h3,TimeoutException(),TimeoutException()]);state=dict(productive=False)
a,cap=drain(e,Node(),state);checks['cap_counts_callbacks_and_keeps_productive_cursor']=len(a)==2 and e.calls==2 and state['productive']
b,_=drain(e,Node(),state);checks['cached_tail_timeout_refills_next_set']=len(b)==1 and order==['1','2','3'] and e.calls==6
checks['complete_empty_set_ends_refill']=not state['productive']
checks['handler_result_and_original_order']=all(h.results==1 for h in (h1,h2,h3))
e=Executor([ShutdownException()]);a,_=drain(e,Node(),dict(productive=True));checks['shutdown_returns_without_retry']=not a and e.calls==1
error=ValueError('original callback exception');h=Handler('error',error)
try:drain(Executor([h]),Node(),dict(productive=False))
except ValueError as raised:checks['original_handler_exception_propagates']=raised is error and h.results==0
h=Handler('callbackTimeout',TimeoutException('callback-owned timeout'))
try:drain(Executor([h]),Node(),dict(productive=False))
except TimeoutException as raised:checks['callback_timeout_is_not_swallowed_as_wait_timeout']=raised is h.error
result=dict(scope='Exact function AST, controlled public-executor interface only; no ROS init/Node/GZ/NN',checks=checks,status='PASS' if all(checks.values()) else 'FAIL',calls=dict(Node=0,Gazebo=0,NN=0))
Path(__file__).with_name('PRODUCTIVE_REFILL_CHECK.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));raise SystemExit(0 if all(checks.values()) else 1)
