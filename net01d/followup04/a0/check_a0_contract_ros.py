"""Inert new-contract A0 typed-DDS interface fixture; no physical/model proof."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile,DurabilityPolicy
from rclpy.serialization import deserialize_message
from rclpy.signals import SignalHandlerOptions
from rclpy.task import Future
from builtin_interfaces.msg import Time
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
from nav2_msgs.action import NavigateToPose
from nav2_msgs.srv import ManageLifecycleNodes
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String,UInt8MultiArray
from unique_identifier_msgs.msg import UUID
from a0_runtime import A0LocalStop,SafetyRegistry,SafetyClient,install_hq_record_hook
from a0_gateway import DirectReferenceGateway
from bound_peer import BatchBinding
from check_action_wire import ControlledServer
from execution_profile import load_profile
from gateway import Gateway
from topic_wire import flows,qos as flow_qos

REPO=Path(__file__).resolve().parents[3]
PROFILE='controlled1000-clock100-q10ms-pace10-raster-simhealth'
DOMAIN=96
SESSION=2026111154
spec=importlib.util.spec_from_file_location('existing_a0_fixture',
    REPO/'net01d/followup02/a0/check_direct_safety.py')
existing=importlib.util.module_from_spec(spec);spec.loader.exec_module(existing)
save=existing.publish_json


def guardian(directory,deadline):
    context=Context();rclpy.init(context=context,domain_id=DOMAIN,signal_handler_options=SignalHandlerOptions.NO)
    fixture=Node('a0_contract_server_source',context=context)
    nodes={r:Node(f'a0_contract_guard_{r}',context=context,
        parameter_overrides=[Parameter('use_sim_time',value=True)]) for r in (1,2)}
    source_exec=SingleThreadedExecutor(context=context);source_exec.add_node(fixture)
    executors={r:SingleThreadedExecutor(context=context) for r in nodes}
    for r in nodes:executors[r].add_node(nodes[r])
    stops={r:A0LocalStop(nodes[r],r,SESSION,execution_profile=load_profile(PROFILE)) for r in nodes}
    registry=SafetyRegistry(directory/'safety.sock',SESSION,stops)
    owner=SimpleNamespace(r=nodes[1],session_id=SESSION,guards=stops,direct_health=[],direct_masks=[])
    admin_qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
    fixture_clock=fixture.create_publisher(Clock,'/clock',admin_qos)
    admin=fixture.create_publisher(String,'/net01/time_control_state',admin_qos)
    admin_receipts=[]
    def receive_admin(message):
        admin_receipts.append(dict(monotonic_ns=time.monotonic_ns(),data=json.loads(message.data)))
        Gateway.time_control_state(owner,message)
    nodes[1].create_subscription(String,'/net01/time_control_state',receive_admin,admin_qos)
    health_qos=flow_qos(flows(runtime=True)[31])
    health=fixture.create_publisher(String,'/peer_keepout_state',health_qos)
    nodes[1].create_subscription(String,'/peer_keepout_state',
        lambda message:DirectReferenceGateway.receive_direct_health(owner,message),health_qos)
    masks={r:fixture.create_publisher(UInt8MultiArray,f'/net01/tb{r}/peer_mask_bound',admin_qos) for r in (1,2,3)}
    for r in nodes:
        nodes[1].create_subscription(UInt8MultiArray,f'/net01/tb{r}/peer_mask_bound',
            lambda message,r=r:DirectReferenceGateway.receive_direct_bound(owner,r,message),admin_qos)
    binding=BatchBinding(lambda robot,packet:masks[int(robot[2:])].publish(UInt8MultiArray(data=list(packet))),SESSION)
    pauses=[];zeros={r:[] for r in nodes};events=[];entered=set();gate=Future()
    for r in nodes:
        def pause(request,response,r=r):
            pauses.append(dict(robot=r,command=request.command,monotonic_ns=time.monotonic_ns()))
            response.success=True;return response
        fixture.create_service(ManageLifecycleNodes,f'/tb{r}/lifecycle_manager_navigation/manage_nodes',pause)
        fixture.create_subscription(Twist,f'/tb{r}/cmd_vel',lambda msg,r=r:zeros[r].append(msg==Twist()),10)
    class Server(ControlledServer):
        async def goal(self,request):
            entered.add(self.robot)
            events.append(dict(kind='actual_goal_received_before_accept',robot=self.robot,
                monotonic_ns=time.monotonic_ns(),owned=sorted(stops[self.robot].owned)))
            await gate
            events.append(dict(kind='actual_accept_return_after_revoke',robot=self.robot,
                monotonic_ns=time.monotonic_ns(),halted=stops[self.robot].guard.halted,
                fault=stops[self.robot].guard.fault))
            return super().goal(request)
    servers={r:Server(fixture,r) for r in nodes}
    control=dict(session_id=SESSION,mode='RUN',failure=None,authority_exited=False,expected_shutdown=False)
    seq=0;clock_ns=100_000_000_000;next_source=0.;ready=False;status_marker=False
    result=dict(scope='Actual A0 typed DDS/admin and Unix safety interface; synthetic source, PAUSE/zero spies only')
    def interrupted(number,frame):raise InterruptedError(f'guardian signal {number}')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    try:
        while not (directory/'STOP').exists():
            if time.monotonic()>=deadline:raise TimeoutError('Original30wall A0 contract bound')
            now=time.monotonic()
            if now>=next_source:
                next_source=now+.02;clock_ns+=10_000_000
                fixture_clock.publish(Clock(clock=Time(sec=clock_ns//1_000_000_000,nanosec=clock_ns%1_000_000_000)))
                admin.publish(String(data=json.dumps(control)))
                if seq%3==0:
                    stamp=nodes[1].get_clock().now();sim=stamp.nanoseconds/1e9
                    state=dict(ready=True,sequence=seq+1,generated_sim=sim,
                        odom_stamps={r:sim for r in ('tb1','tb2','tb3')},
                        correction_stamps={r:sim for r in ('tb1','tb2','tb3')})
                    for r in ('tb1','tb2','tb3'):
                        grid=OccupancyGrid();grid.header.frame_id='odom';grid.header.stamp=stamp.to_msg()
                        grid.info.resolution=.05;grid.info.width=1;grid.info.height=1;grid.info.origin.orientation.w=1.;grid.data=[0]
                        binding.mask(r,grid)
                    message=String(data=json.dumps(state));binding.health(message);health.publish(message)
                seq+=1
            registry.poll();source_exec.spin_once(timeout_sec=.001)
            for r in nodes:
                # Fixture scheduling only: route1 deliberately observes the
                # real response before taking its already queued active status.
                response_seen=any(a['kind']=='a0_actual_response_evidence' for a in stops[1].records)
                if r!=1 or not gate.done() or response_seen:executors[r].spin_once(timeout_sec=.001)
            registry.poll()
            if not ready and all(s.guard.reason() is None and s.node.get_clock().now().nanoseconds>100_000_000_000
                and s.cancel.service_is_ready() and s.result.service_is_ready() and s.pause.service_is_ready()
                and s.zero.get_subscription_count()>0 for s in stops.values()):
                assert all(s.guard.arm() for s in stops.values())
                save(directory/'ready.json',dict(pid=os.getpid(),domain=DOMAIN,profile=PROFILE,
                    guards={str(r):dict(basis=s.guard.receipt_clock_basis,control=s.guard.control) for r,s in stops.items()}));ready=True
            if entered=={1,2} and control['mode']=='RUN':
                control.update(mode='HOLD',authority_exited=True)
                admin.publish(String(data=json.dumps(control)))
            if entered=={1,2} and not gate.done() and all(s.guard.halted for s in stops.values()):
                events.append(dict(kind='both_normal_revoke_before_actual_accept',monotonic_ns=time.monotonic_ns(),
                    faults={str(r):s.guard.fault for r,s in stops.items()}));gate.set_result(True)
            if not status_marker and servers[2].cancelled and any(a['kind']=='actual_local_cancel_response' for a in stops[2].records):
                save(directory/'STATUS_ROUTE_CANCELLED.json',dict(monotonic_ns=time.monotonic_ns()));status_marker=True
            if not (directory/'LOCAL_DRAINED.json').exists() and all(s.guard.halted and not s.owned
                and all(f.done() for f in s.futures)
                and any(a['kind']=='actual_local_GetResult' and a['status']==5 for a in s.records)
                for s in stops.values()) and not registry.connections:
                save(directory/'LOCAL_DRAINED.json',dict(monotonic_ns=time.monotonic_ns()))
        result.update(guards={str(r):dict(actions=s.records,events=s.guard.events,owned=sorted(s.owned),
            accepted=sorted(s.accepted),terminals=s.terminals,fault=s.guard.fault,halted=s.guard.halted,
            pending=sum(not f.done() for f in s.futures),receipt_clock_basis=s.guard.receipt_clock_basis,
            health_receipt_sim=s.guard.health_receipt_sim,mask_receipt_sim=s.guard.mask_receipt_sim,
            health_receipt_monotonic=s.guard.health_receipt,mask_receipt_monotonic=s.guard.mask_receipt,
            may_send_goal=s.guard.may_send_goal()) for r,s in stops.items()},
            server_cancelled={str(r):v.cancelled for r,v in servers.items()},
            accepted_goals_cdr={str(r):v.accepted for r,v in servers.items()},source_events=events,
            pauses=pauses,zeros={str(r):dict(count=len(v),all_exact=bool(v) and all(v)) for r,v in zeros.items()},
            direct_health=owner.direct_health,direct_masks=owner.direct_masks,admin_receipts=admin_receipts,registry_before_close=registry.snapshot())
    except BaseException as error:result['error']=repr(error);raise
    finally:
        registry.close()
        result['registry_actual_close']=dict(listener_fileno=registry.listener.fileno(),
            remaining_connections=len(registry.connections),socket_exists=registry.path.exists())
        for server in servers.values():server.close()
        result['executor_shutdown']=[source_exec.shutdown(timeout_sec=0)]+[e.shutdown(timeout_sec=0) for e in executors.values()]
        for node in [*nodes.values(),fixture]:node.destroy_node()
        context.shutdown();result['context_ok_after_shutdown']=context.ok()
        save(directory/'result.json',result)


def driver(output,deadline):
    from ros_headquarters import LoggedActionClient
    output.mkdir(parents=True,exist_ok=False);directory=output/'guardian';directory.mkdir()
    (output/'fixture-at-run.py').write_text(Path(__file__).read_text())
    (output/'ADMISSION-at-run.json').write_text(Path(__file__).with_name('ADMISSION.json').read_text())
    command=[sys.executable,'-B',str(Path(__file__).resolve()),'--guardian-directory',str(directory),'--deadline-ns',str(int(deadline*1e9))]
    save(output/'argv.json',dict(argv=command,domain=DOMAIN,session_id=SESSION,deadline_monotonic_ns=int(deadline*1e9)))
    context=Context();executor=None;node=None;process=None;clients={}
    result=dict(status='RUNNING',checks={},profile=PROFILE,scope='ZeroRobot actual A0 DDS/interface; synthetic1cell masks/health/clock, PAUSE/zero spies; noROSphysical/Nav2/ns3/GZ/NN proof')
    def interrupted(number,frame):raise InterruptedError(f'fixture signal {number}')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    def check(name,condition):assert condition,name;result['checks'][name]=True;print('PASS',name,flush=True)
    def until(predicate):
        while not predicate():
            if time.monotonic()>=deadline:raise TimeoutError('Original30wall A0 fixture bound')
            executor.spin_once(timeout_sec=.002)
    try:
        with (output/'guardian.log').open('x') as log:process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        rclpy.init(context=context,domain_id=DOMAIN,signal_handler_options=SignalHandlerOptions.NO)
        node=existing.HQFixture(context,output)
        node.allocator.robots['tb2']=SimpleNamespace(token=1,target=(2.,2.))
        executor=SingleThreadedExecutor(context=context);executor.add_node(node)
        clients={r:LoggedActionClient(node,NavigateToPose,f'/tb{r}/navigate_to_pose') for r in (1,2)}
        until(lambda:(directory/'ready.json').exists() and all(c.server_is_ready() for c in clients.values()))
        class OrderedEvidence(SafetyClient):
            def call(self,row,kind):
                if kind=='response' and row['robot']=='tb2':
                    while not (directory/'STATUS_ROUTE_CANCELLED.json').exists():
                        if time.monotonic()>=deadline:raise TimeoutError('status evidence did not cancel before delayed response')
                        time.sleep(.002)
                return super().call(row,kind)
        install_hq_record_hook(node,OrderedEvidence(directory/'safety.sock',SESSION))
        goals={};requests={};handles={};uuids={}
        for r in (1,2):
            goal=NavigateToPose.Goal();goal.pose.header.frame_id='map';goal.pose.header.stamp.sec=100
            goal.pose.pose.position.x=r+.125;goal.pose.pose.orientation.w=1.;goal.behavior_tree='a0-normal-revoke-fixture'
            goals[r]=goal;uuid=UUID(uuid=list(bytes([14,r])+bytes(range(2,16))));uuids[r]=bytes(uuid.uuid).hex()
            requests[r]=clients[r].send_goal_async(goal,goal_uuid=uuid)
        until(lambda:all(f.done() for f in requests.values()))
        for r in (1,2):
            handles[r]=requests[r].result();check(f'tb{r}_actualaccepted_exact_originalUUID',handles[r].accepted and bytes(handles[r].goal_id.uuid).hex()==uuids[r])
        results={r:h.get_result_async() for r,h in handles.items()};until(lambda:all(f.done() for f in results.values()))
        for r,future in results.items():
            check(f'tb{r}_actual_matching_GetResult5',future.result().status==5)
            node.record(dict(kind='rl_actual_nav2_goal_result',sim=node.now(),robot=f'tb{r}',token=1,request_uuid=uuids[r],raw_status=future.result().status))
        # Wait for actual local GetResult/PAUSE and terminal callback drain.
        until(lambda:(directory/'LOCAL_DRAINED.json').exists())
        save(directory/'STOP',dict(monotonic_ns=time.monotonic_ns()))
        process.wait(timeout=max(.01,deadline-time.monotonic()))
        actual=json.loads((directory/'result.json').read_text());check('guardian_actualexit0',process.returncode==0)
        for r in (1,2):
            g=actual['guards'][str(r)];actions=g['actions']
            check(f'tb{r}_faultfree_normal_revoke_no_rearm',g['fault'] is None and g['halted'] and not g['may_send_goal'])
            check(f'tb{r}_exactUUID_one_real_cancel',actual['server_cancelled'][str(r)]==[uuids[r]] and
                [a['uuid'] for a in actions if a['kind']=='actual_local_cancel_response']==[uuids[r]])
            check(f'tb{r}_actual_local_GetResult5_and_pending0',any(a['kind']=='actual_local_GetResult' and a['uuid']==uuids[r] and a['status']==5 for a in actions) and g['pending']==0)
            check(f'tb{r}_real_zero_and_PAUSE_spy',actual['zeros'][str(r)]['all_exact'] and any(a['robot']==r and a['command']==ManageLifecycleNodes.Request.PAUSE for a in actual['pauses']))
            check(f'tb{r}_Goal_fields_exact',len(actual['accepted_goals_cdr'][str(r)])==1 and deserialize_message(bytes.fromhex(actual['accepted_goals_cdr'][str(r)][0]),NavigateToPose.Goal)==goals[r])
        a1=actual['guards']['1']['actions'];a2=actual['guards']['2']['actions']
        response_index=next(i for i,a in enumerate(a1) if a['kind']=='a0_actual_response_evidence')
        check('A0_response_override_before_active_sameUUID_cancel',response_index<next(i for i,a in enumerate(a1) if a['kind']=='actual_local_cancel_response')
            and not any(a['kind']=='a0_actual_active_status' for a in a1[:response_index]))
        check('A0_active_status_override_before_response_sameUUID_cancel',next(i for i,a in enumerate(a2) if a['kind']=='a0_actual_active_status')<next(i for i,a in enumerate(a2) if a['kind']=='actual_local_cancel_response')<next(i for i,a in enumerate(a2) if a['kind']=='a0_actual_response_evidence'))
        check('both_actual_accept_after_faultfree_revoke',sum(a['kind']=='actual_accept_return_after_revoke' and a['halted'] and a['fault'] is None for a in actual['source_events'])==2)
        check('actual_directhealth_bound_admin_newprofile',bool(actual['direct_health']) and bool(actual['direct_masks'])
            and any(a['data']['mode']=='HOLD' and a['data']['authority_exited'] for a in actual['admin_receipts'])
            and all(g['fault'] is None and g['receipt_clock_basis']=='R-ros-sim-v1'
                and g['health_receipt_sim'] is not None and g['mask_receipt_sim'] is not None for g in actual['guards'].values()))
        before=actual['registry_before_close'];closed=actual['registry_actual_close']
        check('exactly_two_originalUUID_registrations',len(before['registrations'])==2
            and {(r['robot'],r['uuid']) for r in before['registrations']}=={(r,uuids[r]) for r in (1,2)})
        check('actual_registry_empty_and_listener_closed',not any(before['owned_unknown_or_active'].values()) and before['connections']==0 and closed==dict(listener_fileno=-1,remaining_connections=0,socket_exists=False))
        check('actual_context_and_executors_closed',all(actual['executor_shutdown']) and not actual['context_ok_after_shutdown'])
        result.update(status='PASS_A0_INTERFACE_ONLY',uuids=uuids,guardian_exit=process.returncode,actual=actual)
    except BaseException as error:result.update(status='FAIL_FIRST_ERROR_PRESERVED',error=repr(error));raise
    finally:
        if process is not None and process.poll() is None:
            if not (directory/'STOP').exists():save(directory/'STOP',dict(reason='fixture_cleanup'))
            try:process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=1)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=1)
        for c in clients.values():c.destroy()
        if executor is not None:executor.shutdown(timeout_sec=0)
        if node is not None:node.events.close();node.destroy_node()
        if context.ok():context.shutdown()
        result['owned_guardian_gone']=process is None or process.poll() is not None
        save(output/'result.json',result)
    return 0


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path)
    parser.add_argument('--guardian-directory',type=Path);parser.add_argument('--deadline-ns',type=int)
    args=parser.parse_args()
    if args.guardian_directory:return guardian(args.guardian_directory,args.deadline_ns/1e9)
    admission=json.loads(Path(__file__).with_name('ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True:parser.error('Root admission required')
    return driver(args.output,time.monotonic()+30)


if __name__=='__main__':raise SystemExit(main())
