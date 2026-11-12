"""External adaptation around the frozen runner, not a copy of its policy/gates.

R runtime halt records come only from received ROS flow95. Source C journal is
read only by the unchanged stop/final ownership routines after authority exit.
"""
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

HERE=Path(__file__).resolve().parent
FROZEN=HERE.parent/"workspace"
for path in (FROZEN/"gz01",FROZEN/"rl04",FROZEN/"rl02",FROZEN/"rl01",FROZEN/"src/multi_robot_exploration"):
    sys.path.insert(0,str(path))
import run_case as original
import rclpy
from std_msgs.msg import String
from std_srvs.srv import Trigger,Empty,SetBool
from rcl_interfaces.srv import GetParameters
from rclpy.qos import QoSProfile,DurabilityPolicy
from execution_profile import load_profile


class NetworkObserver(original.Observer):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        global observer
        observer=self
        self.network_state=None;self.network_received=None;self.received_controller=[]
        self.network_fault=None
        profile=load_profile(os.environ.get('NET01_EXECUTION_PROFILE') or None)
        self.sim_health=(profile is not None and profile.get('health_mask_receipt_clock')=='R-ros-sim-v1')
        self.peer_received_sim=None
        self.controlled_time=os.environ.get('NET01_TIME_CONTROL')=='1'
        self.direct_reference=os.environ.get('NET01_DIRECT_REFERENCE')=='1'
        self.time_control_records=[]
        self.time_stop_results=[];self.last_stop_result=None;self.current_stop_evidence=None
        self.final_stop_phase=False;self.last_time_control_state=None
        self.gateway_evidence_wall_s=(0 if profile is None else
            profile.get('gateway_poststop_evidence_total_wall_s',0))
        self.gateway_evidence_eligible=False;self.gateway_cleanup_deadline_ns=None
        self.gateway_shutdown_started_ns=None
        if self.gateway_evidence_wall_s:
            self.gateway_hard_deadline_ns=min(int(os.environ['NET01_RUNNER_WORK_DEADLINE_NS']),
                int(os.environ['NET01_HOST_HARD_DEADLINE_NS']))
            self.gateway_cleanup_wall_s=float(os.environ['NET01_RUNNER_CLEANUP_WALL_S'])
        self.subscriptions_kept.extend([
            self.create_subscription(String,"/net01/gateway_state",self.network_status,
                QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)),
            self.create_subscription(String,"/net01/guard_fault",self.guard_fault,10),
            self.create_subscription(String,"/net01/controller_records",self.controller_record,100)])

    def network_status(self,message):
        self.network_state=json.loads(message.data);self.network_received=time.monotonic()

    def guard_fault(self,message):
        self.network_fault=message.data
        self.event("network_guard_actual_fault",detail=message.data)

    def controller_record(self,message):
        self.received_controller.append(json.loads(message.data))

    def event(self,kind,**fields):
        if kind=='process_signal' and fields.get('process')=='exploration':
            fields['controller_signal_event_monotonic_ns']=time.monotonic_ns()
        super().event(kind,**fields)
        if kind=='observed_stop' and self.controlled_time:self.current_stop_evidence=fields

    def time_control_call(self,name,service_type,request,timeout=6):
        response=super().call(service_type,'/net01/time_control/'+name,request,timeout=timeout)
        state=json.loads(response.message)
        row=dict(operation=name,success=response.success,state=state,
            monotonic_ns=time.monotonic_ns())
        self.time_control_records.append(row);self.event('actual_time_control_response',**row)
        if state['session_id']!=int(os.environ['NET01_SESSION_ID']):
            raise RuntimeError('Time coordinator session mismatch')
        self.last_time_control_state=state
        if not response.success:raise RuntimeError('Time coordinator refused '+name+': '+response.message)
        return response

    def call(self,service_type,name,request,timeout=6):
        if self.controlled_time and service_type is Empty:
            if name=='/pause_physics':
                return self.pause_with_hold(time.monotonic()+timeout)
            if name=='/unpause_physics':
                self.time_control_call('run',Trigger,Trigger.Request(),timeout=timeout)
                return Empty.Response()  # Controlled RUN permission, never free-running physics.
        return super().call(service_type,name,request,timeout=timeout)

    def pause_with_hold(self,deadline):
        first_error=None;response=None
        try:
            self.time_control_call('hold',SetBool,SetBool.Request(data=False),
                timeout=max(0.,deadline-time.monotonic())/2)
        except Exception as error:
            first_error=error;self.event('time_control_hold_failed',detail=repr(error))
        try:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise RuntimeError('Original physics pause deadline exhausted')
            response=super().call(Empty,'/pause_physics',Empty.Request(),timeout=remaining)
            self.event('time_control_actual_physics_pause_completed')
        except Exception as error:
            self.event('time_control_actual_physics_pause_failed',detail=repr(error))
            if first_error is None:first_error=error
        if first_error is not None:raise first_error
        return response

    def stop_motion(self):
        if not self.controlled_time:return super().stop_motion()
        row=dict(stage='final' if self.final_stop_phase else 'preflight',entered_phase=self.phase,
            success=False,authority_basis='not_created' if controller_process is None else 'actual_process_poll',
            authority_pid=None if controller_process is None else controller_process.pid,
            authority_exit=None if controller_process is None else controller_process.poll())
        self.current_stop_evidence=None
        if self.controlled_time:
            exited=controller_process is None or controller_process.poll() is not None
            self.event('time_control_authority_evidence',basis=('not_created' if controller_process is None else 'actual_process_poll'),
                pid=None if controller_process is None else controller_process.pid,
                native_exit=None if controller_process is None else controller_process.poll(),
                original_authority_stopped=self.authority_stopped)
            try:
                self.time_control_call('stop_observe',SetBool,
                    SetBool.Request(data=self.authority_stopped and exited))
            except Exception as error:
                # Original cancel/zero/PAUSE and its physical stop attempt must
                # still run; an admin failure cannot skip those safety actions.
                self.event('time_control_stop_permission_failed',detail=repr(error))
                self.hazard=self.hazard or 'Controlled stop permission failed: '+repr(error)
        try:
            row['success']=super().stop_motion()
            return row['success']
        except BaseException as error:
            row['error']=repr(error);raise
        finally:
            row.update(observed_stop=self.current_stop_evidence,completed_monotonic_ns=time.monotonic_ns())
            self.last_stop_result=row;self.time_stop_results.append(row)

    def seal_time_control(self):
        deadline=time.monotonic()+6
        last=self.last_stop_result or {};evidence=last.get('observed_stop') or {}
        healthy=(not self.hazard and not self.network_fault and self.last_time_control_state is not None
            and self.last_time_control_state['failure'] is None)
        valid=(last.get('stage')=='final' and last.get('success') is True
            and evidence.get('authority_stopped') is True and evidence.get('ownership_closed') is True
            and evidence.get('request_ownership',{}).get('closed') is True
            and evidence.get('lifecycle_pause_healthy') is True
            and self.paused_robots==set(original.ROBOTS) and self.authority_stopped
            and (controller_process is None or controller_process.poll() is not None) and healthy)
        required={'C_pending','R_pending','C_service_inflight','C_retired_services',
            'local_cleanup_pending','C_unadmitted_unknown_total'}
        if self.direct_reference:
            required.update({'A0_registered_owned_unknown_or_active','A0_safety_connections'})
        drained=False;last_counts=None;first_error=None
        # Reserve half of the original six-second total for HOLD and actual
        # pause; drain does not acquire a separate extension of this deadline.
        drain_until=deadline-3
        if valid:
            while time.monotonic()<drain_until:
                state=self.network_state
                if (state is not None and state['session_id']==int(os.environ['NET01_SESSION_ID'])
                    and state['gateway_monotonic_ns']>last['completed_monotonic_ns']
                    and time.monotonic()-self.network_received<=.3):
                    last_counts=state.get('actual_rpc_cleanup')
                    if (last_counts is not None and required.issubset(last_counts)
                        and all(value==0 for value in last_counts.values())):
                        drained=True;break
                self.stop_zeros();rclpy.spin_once(self,timeout_sec=min(.02,max(0.,drain_until-time.monotonic())))
        if not valid or not drained:
            first_error=RuntimeError('Expected seal lacks final physical stop/authority/RPC closure')
        if self.network_fault or (self.network_state is not None and
            (self.network_state['failure'] or any(g['fault'] for g in self.network_state['guards'].values()))):
            first_error=first_error or RuntimeError('Network failed during shutdown drain')
        self.event('time_control_seal_evidence',valid_final_stop=valid,rpc_drained=drained,
            actual_rpc_cleanup=last_counts,last_stop=last)
        try:self.pause_with_hold(deadline)
        except Exception as error:
            if first_error is None:first_error=error
        if self.last_time_control_state is not None and self.last_time_control_state['failure'] is not None:
            first_error=first_error or RuntimeError('Coordinator failure forbids expected seal')
        # Expected shutdown is committed only after the real stop/drain and
        # resource-HOLD/actual-pause acknowledgements have all succeeded.
        if first_error is None:
            remaining=deadline-time.monotonic()
            if remaining<=0:first_error=RuntimeError('Original seal deadline exhausted')
            else:
                try:self.time_control_call('hold',SetBool,SetBool.Request(data=True),timeout=remaining)
                except Exception as error:first_error=error
        if first_error is not None:raise first_error

    def peer_health(self,message):
        super().peer_health(message)  # Retain original monotonic receipt/event fields.
        if self.sim_health:
            self.peer_received_sim=self.get_clock().now().nanoseconds/1e9
            self.event('peer_receipt_clock',receipt_clock_basis='R-ros-sim-v1',
                received_R_ros_sim=self.peer_received_sim,received_monotonic=self.peer_received,
                sequence=self.peer_state['sequence'])

    def sim_peer_error(self):
        if not self.peer_guard:return None
        if self.peer_state is None or self.sim is None or self.peer_received_sim is None:return 'peer state/clock missing'
        now=self.get_clock().now().nanoseconds/1e9
        age=now-self.peer_received_sim
        wall_age=time.monotonic()-self.peer_received
        if age>.3:
            self.event('peer_heartbeat_stale_context',sequence=self.peer_state['sequence'],
                generated_sim=self.peer_state['generated_sim'],observer_sim=self.sim,
                receipt_clock_basis='R-ros-sim-v1',heartbeat_sim_age=age,heartbeat_wall_age=wall_age,
                end_to_end_fresh=original.state_fresh(self.peer_state,self.sim),
                peer_ready=self.peer_state['ready'],failures=self.peer_state['failures'])
            return 'peer state heartbeat stale'
        if not original.state_fresh(self.peer_state,self.sim):
            return 'peer odom/source-time TF not fresh: '+str(dict(
                sequence=self.peer_state['sequence'],generated_sim=self.peer_state['generated_sim'],
                observer_sim=self.sim,heartbeat_sim_age=age,heartbeat_wall_age=wall_age,
                consumer_ages={r:dict(source=self.sim-self.peer_state['odom_stamps'][r],
                    correction=self.sim-self.peer_state['correction_stamps'][r]) for r in original.ROBOTS
                    if r in self.peer_state['odom_stamps'] and r in self.peer_state['correction_stamps']},
                ages=self.peer_state['ages'],failures=self.peer_state['failures']))
        return None

    def peer_error(self):
        error=self.sim_peer_error() if self.sim_health else super().peer_error()
        if error:return error
        if self.network_fault:return "Network guardian INVALID: "+self.network_fault
        if self.network_state is None:return "Network gateway state missing"
        if time.monotonic()-self.network_received>.3:return "Network gateway receipt stale"
        if self.network_state["failure"]:return "Network gateway INVALID: "+self.network_state["failure"]
        if self.direct_reference and self.network_state.get("direct_reference") is not True:
            return "A0 direct ownership/control status missing"
        if not self.network_state["connected"]:return "Actual delivery link not qualified"
        for robot,guard in self.network_state["guards"].items():
            if guard["fault"]:return f"STA{robot} INVALID: "+guard["fault"]
            if guard["reason"]:return f"STA{robot} unready: "+guard["reason"]
        return None

    def startup_navigation(self,deadline):
        # One real, no-goal clock/pause test inside this admitted Gazebo start.
        profile=load_profile(os.environ.get('NET01_EXECUTION_PROFILE') or None)
        quantum_sim_s=.1 if profile is None else profile['native_step_quantum_ns']/1e9
        if profile is not None:
            response=self.call(GetParameters,'/gazebo/get_parameters',GetParameters.Request(names=['publish_rate']))
            actual=response.values[0].double_value
            self.event('network_execution_clock_parameter',node='/gazebo',parameter='publish_rate',
                expected=profile['clock_publish_rate_sim_hz'],actual=actual,profile=profile['id'])
            if actual!=profile['clock_publish_rate_sim_hz']:
                raise RuntimeError('Actual gazebo publish_rate differs from admitted execution profile')
        def reject_latched_failure():
            if self.network_fault:raise RuntimeError('Network guardian INVALID: '+self.network_fault)
            state=self.network_state
            if state is not None:
                if state['failure']:raise RuntimeError('Network gateway INVALID: '+state['failure'])
                for robot,guard in state['guards'].items():
                    if guard['fault']:raise RuntimeError(f'STA{robot} INVALID: '+guard['fault'])
        request_ns=time.monotonic_ns()
        self.call(Empty,"/pause_physics",Empty.Request())
        completed_ns=time.monotonic_ns()
        try:
            while time.monotonic()<deadline:
                rclpy.spin_once(self,timeout_sec=.01)
                reject_latched_failure()
                state=self.network_state
                if (state is not None and state['gateway_monotonic_ns']>completed_ns
                    and time.monotonic()-self.network_received<=.3 and state['anchor'] is not None
                    and state['gz_ns']==int(round(self.sim*1e9))
                    and state['ns3_ns']==state['gz_ns']-state['anchor']['offset_ns']):break
            else:raise RuntimeError("Original startup deadline: no fresh aligned post-pause clock baseline")
            before=dict(self.network_state);baseline_ns=time.monotonic_ns();baseline_R_sim=self.sim
            until=time.monotonic()+.35
            if until>deadline:raise RuntimeError("Original startup deadline leaves no pause observation window")
            while time.monotonic()<until:
                rclpy.spin_once(self,timeout_sec=.01)
                reject_latched_failure()
            paused=dict(self.network_state);observed_ns=time.monotonic_ns();observed_R_sim=self.sim
        finally:self.call(Empty,"/unpause_physics",Empty.Request())
        anchor=before["anchor"]
        if not anchor or paused["anchor"]!=anchor:raise RuntimeError("Network clock anchor changed")
        if paused["gz_ns"]-before["gz_ns"]>100_000_000:
            raise RuntimeError("Gazebo /clock exceeded legacy .1sim pause advance bound")
        if paused["ns3_ns"]>paused["gz_ns"]-anchor["offset_ns"]:
            raise RuntimeError("ns-3 advanced beyond actual Gazebo clock")
        if paused["ns3_ns"]-before["ns3_ns"]>100_000_000:
            raise RuntimeError("ns-3 progressed during Gazebo pause beyond legacy .1sim advance bound")
        self.event("real_clock_no_goal_pause_resume",before=before,paused=paused,
            pause_request_monotonic_ns=request_ns,pause_completed_monotonic_ns=completed_ns,
            baseline_monotonic_ns=baseline_ns,observed_monotonic_ns=observed_ns,
            baseline_R_sim=baseline_R_sim,observed_R_sim=observed_R_sim,
            test_wall_s=.35,quantum_sim_s=quantum_sim_s,legacy_pause_advance_bound_sim_s=.1,max_lag_sim_s=.12)
        while time.monotonic()<deadline:
            rclpy.spin_once(self,timeout_sec=.01)
            reject_latched_failure()
            if not self.peer_error():break
        else:raise RuntimeError("Original startup deadline: no fresh sources after clock resume")
        super().startup_navigation(deadline)

    def resume(self):
        if self.controlled_time:self.call(Empty,'/unpause_physics',Empty.Request())
        super().resume()
        for robot in (1,2,3):
            response=self.call(Trigger,f"/net01/tb{robot}/arm",Trigger.Request())
            self.event("network_local_arm",robot=robot,success=response.success,detail=response.message)
            if not response.success:raise RuntimeError("Actual STA guard refused arm: "+str(robot))

    def persist_observer_records(self):
        # Original caller has already stopped controller, bag and launch here.
        if gateway is not None and gateway.poll() is None:original.end_process(gateway,self,"network_gateway")
        (self.directory/"network-gateway-exit.json").write_text(json.dumps(dict(
            native_exit=None if gateway is None else gateway.poll(),
            phase="after_original_stop_and_owned_launch_cleanup_attempts")))
        (self.directory/"network-controller-exit.json").write_text(json.dumps(dict(
            started=controller_process is not None,
            pid=None if controller_process is None else controller_process.pid,
            returncode=None if controller_process is None else controller_process.poll(),
            session_id=int(os.environ['NET01_SESSION_ID']),case=str(self.directory.resolve()),
            observed_monotonic_ns=time.monotonic_ns(),
            phase="after_original_stop_and_owned_launch_cleanup_attempts")))
        (self.directory/"received-controller-records.json").write_text(json.dumps(self.received_controller))
        if self.controlled_time:
            (self.directory/'time-control-observer.json').write_text(json.dumps(dict(
                control_responses=self.time_control_records,stop_attempts=self.time_stop_results),indent=2)+'\n')
        super().persist_observer_records()


observer=None
gateway=None
controller_process=None
frozen_end_process=original.end_process
frozen_controller_end=original.controller_end


def end_controlled_launch(process,observer):
    if process is None or process.poll() is not None:return
    for sig,timeout in ((signal.SIGINT,20),(signal.SIGTERM,5),(signal.SIGKILL,5)):
        target='owned_launch_parent_pid' if sig==signal.SIGINT else 'owned_launch_process_group'
        observer.event('process_signal',process='launch',pid=process.pid,signal=sig.name,
            signal_target=target,timeout_wall_s=timeout)
        # ROSlaunch forwards the first SIGINT itself. Sending it to the whole
        # group as well would interrupt each child's finally/persistence twice.
        if sig==signal.SIGINT:os.kill(process.pid,sig)
        else:os.killpg(process.pid,sig)
        until=time.monotonic()+timeout
        while process.poll() is None and time.monotonic()<until:
            observer.stop_zeros()
            rclpy.spin_once(observer,timeout_sec=.02)
        if process.poll() is not None:
            observer.event('process_exit',process='launch',code=process.returncode)
            return


def gateway_closed_proof(process,observer,begin_ns,initial_deadline_ns):
    path=observer.directory/'network-gateway-resources-closed.json'
    try:row=json.loads(path.read_text())
    except FileNotFoundError:return None
    except json.JSONDecodeError:return None
    if (row.get('phase')!='resources_closed' or row.get('safe_closed') is not True
        or row.get('pid')!=process.pid or row.get('session_id')!=int(os.environ['NET01_SESSION_ID'])
        or row.get('case')!=str(observer.directory.resolve())
        or not begin_ns<=row.get('monotonic_ns',0)<=initial_deadline_ns):return None
    cleanup=row.get('cleanup',{})
    sampler=cleanup.get('main_thread_sampler')
    if (cleanup.get('resources_destroyed') is not True or cleanup.get('end_frame_flushed') is not True
        or cleanup.get('executor_shutdown')!=[True,True]
        or cleanup.get('unresolved_C_RPC')!=[] or cleanup.get('unresolved_R_RPC')!=[]
        or any(cleanup.get('unresolved_local_cleanup_futures',{'missing':1}).values())
        or (sampler is not None and (not sampler['joined'] or sampler['failure'] is not None))):return None
    states=cleanup.get('action_confirmation_states')
    if states is not None and any(state['waiting'] or state['unconfirmed']
        for state in (states['C'],*states['R'].values())):return None
    return row


def end_gateway(process,observer):
    if process is None or process.poll() is not None:return
    if not observer.gateway_evidence_wall_s:
        return frozen_end_process(process,observer,'network_gateway')
    if observer.gateway_shutdown_started_ns is None:
        observer.gateway_shutdown_started_ns=time.monotonic_ns()
    begin_ns=observer.gateway_shutdown_started_ns
    # Fixed once: all phases share the same total, cleanup and parent bounds.
    total_deadline_ns=min(begin_ns+int(observer.gateway_evidence_wall_s*1e9),
        observer.gateway_hard_deadline_ns,
        observer.gateway_cleanup_deadline_ns or observer.gateway_hard_deadline_ns)
    initial_deadline_ns=min(begin_ns+20_000_000_000,total_deadline_ns-10_000_000_000)
    eligible=(observer.gateway_evidence_eligible and observer.authority_stopped
        and (controller_process is None or controller_process.poll() is not None))
    proof=None
    effective_total_ns=min(begin_ns+30_000_000_000,total_deadline_ns)
    observer.event('gateway_poststop_supervision',pid=process.pid,begin_monotonic_ns=begin_ns,
        initial_deadline_ns=initial_deadline_ns,total_deadline_ns=total_deadline_ns,
        cleanup_deadline_ns=observer.gateway_cleanup_deadline_ns,
        hard_deadline_ns=observer.gateway_hard_deadline_ns,extension_eligible=eligible)
    for sig,deadline_ns in ((signal.SIGINT,initial_deadline_ns),
            (signal.SIGTERM,None),(signal.SIGKILL,None)):
        if sig==signal.SIGTERM:
            deadline_ns=min(time.monotonic_ns()+5_000_000_000,effective_total_ns-5_000_000_000)
        elif sig==signal.SIGKILL:
            deadline_ns=min(time.monotonic_ns()+5_000_000_000,effective_total_ns)
        observer.event('process_signal',process='network_gateway',pid=process.pid,signal=sig.name,
            deadline_monotonic_ns=deadline_ns)
        os.killpg(process.pid,sig)
        while process.poll() is None:
            now_ns=time.monotonic_ns()
            if sig==signal.SIGINT and eligible and proof is None:
                proof=gateway_closed_proof(process,observer,begin_ns,initial_deadline_ns)
                if proof is not None:
                    effective_total_ns=total_deadline_ns
                    deadline_ns=total_deadline_ns-10_000_000_000
                    observer.event('gateway_evidence_grace',pid=process.pid,
                        resources_closed=proof,grace_deadline_ns=deadline_ns,
                        total_deadline_ns=total_deadline_ns)
            if now_ns>=deadline_ns:break
            observer.stop_zeros()
            rclpy.spin_once(observer,timeout_sec=min(.02,(deadline_ns-now_ns)/1e9))
        if process.poll() is not None:
            observer.event('process_exit',process='network_gateway',code=process.returncode)
            return


def end_process(process,observer,name):
    if name=='exploration':
        observer.final_stop_phase=True
        if observer.gateway_evidence_wall_s and observer.gateway_cleanup_deadline_ns is None:
            observer.gateway_cleanup_deadline_ns=time.monotonic_ns()+int(observer.gateway_cleanup_wall_s*1e9)
    if name=='network_gateway':return end_gateway(process,observer)
    if name=='launch' and process is not None and observer.controlled_time:
        try:
            observer.seal_time_control()
            observer.gateway_evidence_eligible=True
        except Exception as error:
            observer.event('time_control_seal_failed',detail=repr(error))
            observer.hazard=observer.hazard or 'Controlled-time seal failed: '+repr(error)
        # Keep actual Nav2/plugin services alive through the Gateway's real
        # cancellation/GetResult cleanup and END flush, then destroy launch.
        end_gateway(gateway,observer)
        observer.event('network_gateway_before_launch_exit',
            native_exit=None if gateway is None else gateway.poll())
        return end_controlled_launch(process,observer)
    return frozen_end_process(process,observer,name)


def received_controller_end(directory,position):
    rows=observer.received_controller
    while position<len(rows):
        row=rows[position];position+=1
        if row.get("kind")=="rl_halt_requested":return row["reason"],position
    return None,position


def popen(command,*args,**kwargs):
    global gateway,controller_process
    command=list(command)
    authority=False
    if command[:2]==["ros2","launch"]:
        if command[2]!=str(FROZEN/"gz01/scene_launch.py"):
            raise RuntimeError("Unexpected launch source at external adapter")
        command[2]=str(HERE/"net_scene_launch.py")
        if os.environ.get("NET01_COMMON_EXECUTION_REVISION")=="static-footprint-common-v1":
            command[2]=str(HERE.parent/"net01e/followup02/static_footprint_launch.py")
        if observer.controlled_time:
            command.insert(2,"--noninteractive")
        log=(observer.directory/"network-gateway.log").open("x")
        gateway_entry=HERE/("a0_gateway.py" if observer.direct_reference else "gateway.py")
        if os.environ.get('NET01_RAW_DESTINATION')=='1':
            gateway_entry=HERE.parent/'net01e/followup01/production_gateway.py'
        gateway=subprocess.Popen([sys.executable,"-B",str(gateway_entry),
            "--mode",os.environ["NET01_MODE"],"--socket",os.environ["NET01_SOCKET"],
            "--session-id",os.environ["NET01_SESSION_ID"],"--directory",str(observer.directory)]+
            (['--control-trace'] if os.environ['NET01_CONTROL_TRACE']=='1' else [])+
            (['--dispatch-profile'] if os.environ.get('NET01_DISPATCH_PROFILE')=='1' else [])+
            (['--main-thread-sample'] if os.environ.get('NET01_MAIN_THREAD_SAMPLE')=='1' else [])+
            (['--adapter-qos-events',os.environ['NET01_ADAPTER_QOS_EVENTS']]
                if os.environ.get('NET01_ADAPTER_QOS_EVENTS','sdk-default')!='sdk-default' else [])+
            (['--capture-central-map'] if os.environ.get('NET01_CAPTURE_CENTRAL_MAP')=='1' else [])+
            (['--execution-profile',os.environ['NET01_EXECUTION_PROFILE']] if os.environ.get('NET01_EXECUTION_PROFILE') else []),
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        original.record_process(observer.directory,"network_gateway",gateway.pid)
    elif len(command)>2 and command[:2]==["python3","-B"] and command[2]==str(FROZEN/"gz01/headquarters.py"):
        authority=True
        command[2]=str(HERE/("a0_controller_bootstrap.py" if observer.direct_reference else "controller_bootstrap.py"))
        if os.environ.get('NET01_CONTROLLER_EXIT_ADAPTER')=='net01e-graceful-v1':
            command[2]=str(HERE.parent/'net01e/controller/graceful_controller_bootstrap.py')
        kwargs["env"]=dict(os.environ,ROS_DOMAIN_ID="92" if observer.direct_reference else "91")
    elif command[:3]==["ros2","bag","record"]:
        index=command.index("--qos-profile-overrides-path")
        if command[index+1]!=str(FROZEN/"rl02/bag-qos.yaml"):
            raise RuntimeError("Unexpected frozen recorder QoS path")
        command[index+1]=str(HERE/"config/recorder-qos.yaml")
    process=subprocess.Popen(command,*args,**kwargs)
    if authority:controller_process=process
    return process


def main():
    # Frozen validate_ready/stop/policy source remain intact. This supplies only
    # the explicit transport composition and the received halt-input adapter.
    original.Observer=NetworkObserver
    original.controller_end=(frozen_controller_end if os.environ.get("NET01_DIRECT_REFERENCE")=="1"
        else received_controller_end)
    original.end_process=end_process
    original.subprocess=SimpleNamespace(Popen=popen,run=subprocess.run,STDOUT=subprocess.STDOUT,
        TimeoutExpired=subprocess.TimeoutExpired)
    return original.main()


if __name__=="__main__":raise SystemExit(main())
