"""Exact actual async controller methods with a controlled Future, 0Node/ROS.

AST extraction avoids importing rclpy; it does not replace method bodies.
"""
import argparse
import ast
import asyncio
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from time_control_state import TimeControlState,QUANTUM_NS
from execution_profile import load_profile,CONTROLLED_PROFILE_IDS


async def check():
    source=ast.parse((HERE/'time_controller.py').read_text())
    original=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='TimeController')
    names={'hold','run','stop_observe','finish_step','snapshot'}
    methods=[n for n in original.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
    actual=ast.ClassDef(name='ActualMethods',bases=[],keywords=[],body=methods,decorator_list=[])
    namespace={'json':json,'time':time,'QUANTUM_NS':QUANTUM_NS};exec(compile(ast.fix_missing_locations(ast.Module(body=[actual],type_ignores=[])),str(HERE/'time_controller.py'),'exec'),namespace)
    node=namespace['ActualMethods']();node.state=TimeControlState();node.state.native('ready',0)
    node.state.gateway_clock_ready=True
    node.state.begin_step(0);node.pending_holds=0;node.records=[]
    node.first_physical_before_ns=None;node.last_physical_ACK_wall_ns=None
    node.first_physical_token_wall_ns=time.monotonic_ns();node.session_id=1
    node.execution_profile=load_profile(CONTROLLED_PROFILE_IDS[0])
    node.record=lambda *values:node.records.append(values)
    pending=node.future=asyncio.get_running_loop().create_future()
    task=asyncio.create_task(node.hold(SimpleNamespace(data=True),SimpleNamespace()))
    await asyncio.sleep(0)
    assert node.pending_holds==1 and not task.done() and node.state.mode=='HOLD'
    assert not node.run(None,SimpleNamespace()).success
    assert not node.stop_observe(SimpleNamespace(data=True),SimpleNamespace()).success
    assert not node.state.can_step(100_000_000) and not node.state.expected_shutdown
    pending.set_result(SimpleNamespace(success=True,message=json.dumps(dict(before_ns=0,after_ns=10_000_000,
        before_iterations=0,after_iterations=10,completed_steps=10))))
    response=await task
    assert response.success and node.pending_holds==0 and not node.state.inflight
    assert node.future is None and node.state.mode=='HOLD' and node.state.expected_shutdown
    assert not node.run(None,SimpleNamespace()).success
    measured=json.loads(response.message)
    assert measured['planned_realtime_factor']==.5 and measured['token_wall_period_ns']==20_000_000
    assert measured['physical_progress_sim_span_ns']==10_000_000 and measured['physical_progress_wall_span_ns']>0
    assert measured['actual_achieved_physical_rtf']==10_000_000/measured['physical_progress_wall_span_ns']
    return dict(scope='Actual AST-extracted async methods; controlled Future; 0Node/ROS/GZ',
        status='PASS',checks=dict(HOLD_await_rejects_RUN_and_STOP=True,
        original_RPC_completes_without_second_token=True,successful_HOLD_has_no_inflight=True,
        expected_shutdown_only_after_completion=True,actual_snapshot_reports_successful_ACK_sim_wall_ratio=True),events=node.records)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=asyncio.run(check());args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
