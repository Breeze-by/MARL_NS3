"""Execute the real fixture ARM/status AST without ROS or navigation Goals."""
import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace

source=Path(__file__).resolve().parents[1]/'health/full_load_source.py'
tree=ast.parse(source.read_text())
main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
callback=copy.deepcopy(next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='gateway_state'))
callback.body=[ast.Global(names=n.names) if isinstance(n,ast.Nonlocal) else n for n in callback.body]
loop=next(n for n in ast.walk(main) if isinstance(n,ast.While))
blocks=[copy.deepcopy(n) for n in loop.body if isinstance(n,ast.If) and
        ('arm_future is None' in ast.unparse(n.test) or 'arm_future.done()' in ast.unparse(n.test))]
assert len(blocks)==2
status_code=compile(ast.fix_missing_locations(ast.Module(body=[callback],type_ignores=[])),str(source),'exec')
arm_code=compile(ast.fix_missing_locations(ast.Module(body=blocks,type_ignores=[])),str(source),'exec')

def fixture(responses):
    records=[];requests=[];pending=iter(responses)
    def call(request):
        requests.append(request);response=next(pending)
        return SimpleNamespace(done=lambda:True,result=lambda:response)
    ns=dict(json=json,status=None,status_revision=0,arm_rejected_revision=-1,
        quiet=False,robot=1,arm_future=None,arm_response=None,
        arm=SimpleNamespace(service_is_ready=lambda:True,call_async=call),
        Trigger=SimpleNamespace(Request=object),record=lambda kind,**kw:records.append(dict(kind=kind,**kw)))
    exec(status_code,ns)
    def status(reason=None,fault=None):
        ns['gateway_state'](SimpleNamespace(data=json.dumps({'guards':{'1':{'reason':reason,'fault':fault}}})))
    return ns,records,requests,status

def response(success,fault=None):
    return SimpleNamespace(success=success,message=json.dumps(dict(robot=1,fault=fault,
        reason=None if success else 'health_original_sources_stale')))

ns,records,requests,status=fixture([response(False),response(True)])
status();exec(arm_code,ns);assert len(requests)==1 and ns['arm_future'] is None
exec(arm_code,ns);assert len(requests)==1  # Same status cannot retry.
status(reason='health_original_sources_stale');exec(arm_code,ns);assert len(requests)==1
status();exec(arm_code,ns);assert len(requests)==2 and ns['arm_response']['success'] is True
exec(arm_code,ns);assert len(requests)==2
assert [r['success'] for r in records if r['kind']=='actual_local_arm_response']==[False,True]
transient_records=records
ns,records,requests,status=fixture([response(False,fault='latched_fault')])
status();exec(arm_code,ns);status();exec(arm_code,ns)
assert len(requests)==1 and ns['arm_response']['success'] is False
result=dict(status='PASS',scope='Actual fixture gateway_state/inline ARM AST; no ROS, models or navigation Goal retries',
    source=str(source),transient_records=transient_records,latched_fault_records=records,
    checks=['transient rejection retained','same snapshot no repeat','new unhealthy snapshot no repeat',
        'new healthy snapshot retries ARM and succeeds','success no repeat','latched rejection never retries'])
output=Path(__file__).with_name('full-source-arm-check.json')
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
