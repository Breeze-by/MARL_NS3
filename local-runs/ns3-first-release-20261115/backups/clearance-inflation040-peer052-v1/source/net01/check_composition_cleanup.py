"""One targeted no-control check: unknown ROS callback teardown + pause baseline.

No WiFi model, Gazebo, Action server, goal, cmd_vel, policy or training starts.
The pause case uses the actual method AST with a controlled time/service source;
it is not a real Gazebo clock certificate.
"""
import argparse
import ast
import json
from pathlib import Path
import time
from types import SimpleNamespace

import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.task import Future
from std_srvs.srv import Empty
from gateway import Gateway


class Hub:
    def __init__(self,fail=False):
        self.outgoing=bytearray();self.deliveries=[];self.fail=fail
    def end(self):self.outgoing.extend(b"END")
    def poll(self):
        if self.fail:raise EOFError("controlled missing native END")
        self.outgoing.clear()
    def close(self):pass


def gateway_object(directory,hub):
    obj=Gateway.__new__(Gateway)
    obj.directory=directory;obj.hub=hub;obj.mode="A";obj.anchor=None;obj.gz=None
    obj.failure=None;obj.records=[];obj.link=SimpleNamespace(events=[])
    obj.guards={};obj.executors=[];obj.nodes=[];obj.contexts=[];obj.wires=None
    return obj


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    checks={};context=Context();rclpy.init(context=context,domain_id=96)
    node=Node("net01_bounded_unknown_callback",context=context)
    executor=SingleThreadedExecutor(context=context);executor.add_node(node)
    entered=[];unknown=Future(executor=executor)
    async def callback(request,response):
        entered.append(True)
        await unknown
        return response
    service=node.create_service(Empty,"/net01/unknown_callback_fixture",callback)
    client=node.create_client(Empty,"/net01/unknown_callback_fixture")
    deadline=time.monotonic()+5
    while not client.service_is_ready() and time.monotonic()<deadline:executor.spin_once(timeout_sec=.01)
    if not client.service_is_ready():raise TimeoutError("Fixture service discovery")
    response=client.call_async(Empty.Request())
    while not entered and time.monotonic()<deadline:executor.spin_once(timeout_sec=.01)
    if not entered:raise TimeoutError("Fixture did not enter suspended service callback")
    directory=args.output/"unknown";directory.mkdir()
    obj=gateway_object(directory,Hub())
    obj.wires={"C":SimpleNamespace(captured=[],delivered=[])}
    obj.action_c=SimpleNamespace(pending={(1,1,123):(response,Empty.Response,1)})
    obj.action_r={};obj.bound_r=SimpleNamespace(received=[])
    obj.executors=[executor];obj.nodes=[node];obj.contexts=[context]
    started=time.monotonic();clean=obj.close();elapsed=time.monotonic()-started
    checks["unknown_callback_real_DDS_entered"]=bool(entered)
    checks["bounded_shutdown_returns_without_fabricated_response"]=elapsed<2 and not response.done() and not unknown.done()
    checks["executor_reported_unfinished_callback"]=obj.cleanup["executor_shutdown"]==[False]
    checks["original_RPC_identity_recorded_unknown"]=obj.cleanup["unresolved_C_RPC"]==[dict(robot=1,flow_offset=1,rpc_id=123)]
    checks["resources_destroyed_before_saved_marker"]=obj.cleanup["resources_destroyed"] and json.loads((directory/"network-gateway-saved.json").read_text())["cleanup"]["resources_destroyed"]
    failed=args.output/"missing_end";failed.mkdir()
    missing=gateway_object(failed,Hub(fail=True))
    checks["missing_END_is_false_not_direct_fallback"]=missing.close() is False and not missing.cleanup["end_frame_flushed"]

    # The actual pause method, with only its enclosing test base replaced.
    tree=ast.parse(Path(__file__).with_name("run_network_case.py").read_text())
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="NetworkObserver")
    method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=="startup_navigation")
    controlled=SimpleNamespace(wall=1.,paused=False)
    class Base:
        def startup_navigation(self,deadline):self.started_with_original_deadline=deadline
    def spin(subject,timeout_sec):
        controlled.wall+=timeout_sec
        subject.network_state=dict(subject.network_state,gateway_monotonic_ns=int(controlled.wall*1e9))
    namespace=dict(original=SimpleNamespace(Observer=Base),rclpy=SimpleNamespace(spin_once=spin),
        time=SimpleNamespace(monotonic=lambda:controlled.wall,monotonic_ns=lambda:int(controlled.wall*1e9)),Empty=Empty)
    extracted=ast.Module(body=[ast.ClassDef(name="NetworkObserver",bases=cls.bases,
        keywords=[],body=[method],decorator_list=[])],type_ignores=[])
    exec(compile(ast.fix_missing_locations(extracted),str(__file__),"exec"),namespace)
    subject=namespace["NetworkObserver"]()
    anchor=dict(offset_ns=100_000_000,monotonic_ns=1)
    subject.network_state=dict(gateway_monotonic_ns=1,gz_ns=100_000_000,ns3_ns=0,anchor=anchor)
    subject.sim=.1;subject.events=[]
    def call(typ,name,request):
        if name=="/pause_physics":
            # A legitimate service/discovery delay advanced the world >.1sim.
            controlled.wall+=.25;subject.sim+=.25
            subject.network_state=dict(subject.network_state,gz_ns=350_000_000,ns3_ns=250_000_000)
    subject.call=call;subject.peer_error=lambda:None
    subject.event=lambda kind,**fields:subject.events.append(dict(kind=kind,**fields))
    subject.startup_navigation(5.)
    row=subject.events[0]
    checks["pause_baseline_after_ack_not_pre_request_cache"]=row["before"]["gz_ns"]==350_000_000 and row["baseline_monotonic_ns"]>row["pause_completed_monotonic_ns"]>row["pause_request_monotonic_ns"]
    checks["pause_observes_full_fixed_window_after_baseline"]=row["observed_monotonic_ns"]-row["baseline_monotonic_ns"]>=350_000_000
    checks["original_startup_deadline_unchanged"]=subject.started_with_original_deadline==5.
    result=dict(status="PASS" if all(checks.values()) else "FAIL",checks=checks,
        shutdown_wall_s=elapsed,actual_ROS_domains=[96],robot_control=False,Gazebo=0,
        scope="Actual suspended non-control DDS service cleanup; controlled pause-method AST only, not TIME/GZ PASS")
    (args.output/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result),flush=True)
    return 0 if all(checks.values()) else 1


if __name__=="__main__":raise SystemExit(main())
