"""No Node: exact diagnostic AST, default-off and original exception semantics."""
import ast,json,time
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[1];tree=ast.parse((root/'gateway.py').read_text())
functions=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ('record_cpu_span','drain_current_ready')]
cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Gateway');methods=[x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name in ('progress_transport','_progress_transport')]
class TimeoutException(Exception):pass
class ShutdownException(Exception):pass
ns=dict(time=time,TimeoutException=TimeoutException,ShutdownException=ShutdownException)
exec(compile(ast.Module(body=functions+methods,type_ignores=[]),'actual_gateway_profile','exec'),ns)
checks={};trace=[]
class Handler:
    def __init__(self,error=None):self.error=error
    def __call__(self):trace.append('handler')
    def exception(self):return self.error
    def result(self):trace.append('result');return None
class Executor:
    def __init__(self,error=None):self.error=error
    def wait_for_ready_callbacks(self,timeout_sec):
        if self.error:raise self.error
        return Handler(),None,None
node=SimpleNamespace(subscriptions=(1,),timers=(),clients=(),services=(),guards=(),waitables=())
a,cap=ns['drain_current_ready'](Executor(),node,dict(productive=False),lambda:trace.append('pump'))
checks['defaultoff_original_handler_result_pump_order']=len(a)==cap==1 and trace==['handler','result','pump']
error=ValueError('actual handler error');profile=dict(wait={},handlers={})
class BrokenExecutor:
    def wait_for_ready_callbacks(self,timeout_sec):return Handler(error),None,None
try:ns['drain_current_ready'](BrokenExecutor(),node,dict(productive=False),lambda:trace.append('must_not_pump'),profile=profile,entity_label=lambda x:'known_entity')
except ValueError as e:checks['profile_handler_error_original_propagation']=e is error and profile['handlers']['known_entity']['calls']==1 and 'must_not_pump' not in trace
error=RuntimeError('actual wait error');profile=dict(wait={},handlers={})
try:ns['drain_current_ready'](Executor(error),node,dict(productive=False),profile=profile,entity_label=lambda x:'not_called')
except RuntimeError as e:checks['profile_wait_error_original_propagation']=e is error and profile['wait']['error']['calls']==1 and not profile['handlers']
s=SimpleNamespace(cpu_profile=None,_progress_transport=lambda:17);checks['defaultoff_progress_returns_original_value']=ns['progress_transport'](s)==17
error=EOFError('actual hub EOF')
class Hub:
    def poll(self):raise error
s=SimpleNamespace(cpu_profile=dict(progress={}),failure=None,hub=Hub());s._progress_transport=lambda:ns['_progress_transport'](s)
try:ns['progress_transport'](s)
except EOFError as e:checks['profile_hub_error_original_propagation']=e is error and s.cpu_profile['progress']['hub_poll']['calls']==1 and s.cpu_profile['progress']['total_inclusive']['calls']==1
checks['profile_categories_do_not_merge_handler_and_progress']='progress' not in profile and set(s.cpu_profile['progress'])=={'hub_poll','total_inclusive'}
r=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,scope='Exact diagnostic function AST; no Node/ROS/Gazebo/NN, no throughput claim',calls=dict(Node=0,Gazebo=0,NN=0))
Path(__file__).with_name('DISPATCH_PROFILE_CHECK.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if all(checks.values()) else 1)
