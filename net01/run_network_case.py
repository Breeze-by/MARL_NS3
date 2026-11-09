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
from std_srvs.srv import Trigger,Empty
from rclpy.qos import QoSProfile,DurabilityPolicy


class NetworkObserver(original.Observer):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        global observer
        observer=self
        self.network_state=None;self.network_received=None;self.received_controller=[]
        self.network_fault=None
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

    def peer_error(self):
        error=super().peer_error()
        if error:return error
        if self.network_fault:return "Network guardian INVALID: "+self.network_fault
        if self.network_state is None:return "Network gateway state missing"
        if time.monotonic()-self.network_received>.3:return "Network gateway receipt stale"
        if self.network_state["failure"]:return "Network gateway INVALID: "+self.network_state["failure"]
        if not self.network_state["connected"]:return "Actual delivery link not qualified"
        for robot,guard in self.network_state["guards"].items():
            if guard["fault"]:return f"STA{robot} INVALID: "+guard["fault"]
            if guard["reason"]:return f"STA{robot} unready: "+guard["reason"]
        return None

    def startup_navigation(self,deadline):
        # One real, no-goal clock/pause test inside this admitted Gazebo start.
        request_ns=time.monotonic_ns()
        self.call(Empty,"/pause_physics",Empty.Request())
        completed_ns=time.monotonic_ns()
        try:
            while time.monotonic()<deadline:
                rclpy.spin_once(self,timeout_sec=.01)
                if self.network_state["gateway_monotonic_ns"]>completed_ns:break
            else:raise RuntimeError("Original startup deadline: no post-pause gateway clock baseline")
            before=dict(self.network_state);baseline_ns=time.monotonic_ns();baseline_R_sim=self.sim
            until=time.monotonic()+.35
            if until>deadline:raise RuntimeError("Original startup deadline leaves no pause observation window")
            while time.monotonic()<until:rclpy.spin_once(self,timeout_sec=.01)
            paused=dict(self.network_state);observed_ns=time.monotonic_ns();observed_R_sim=self.sim
        finally:self.call(Empty,"/unpause_physics",Empty.Request())
        anchor=before["anchor"]
        if not anchor or paused["anchor"]!=anchor:raise RuntimeError("Network clock anchor changed")
        if paused["gz_ns"]-before["gz_ns"]>100_000_000:
            raise RuntimeError("Gazebo /clock did not pause within fixed .1sim quantum")
        if paused["ns3_ns"]>paused["gz_ns"]-anchor["offset_ns"]:
            raise RuntimeError("ns-3 advanced beyond actual Gazebo clock")
        if paused["ns3_ns"]-before["ns3_ns"]>100_000_000:
            raise RuntimeError("ns-3 progressed during Gazebo pause beyond one admitted horizon")
        self.event("real_clock_no_goal_pause_resume",before=before,paused=paused,
            pause_request_monotonic_ns=request_ns,pause_completed_monotonic_ns=completed_ns,
            baseline_monotonic_ns=baseline_ns,observed_monotonic_ns=observed_ns,
            baseline_R_sim=baseline_R_sim,observed_R_sim=observed_R_sim,
            test_wall_s=.35,quantum_sim_s=.1,max_lag_sim_s=.12)
        while time.monotonic()<deadline:
            rclpy.spin_once(self,timeout_sec=.01)
            if not self.peer_error():break
        else:raise RuntimeError("Original startup deadline: no fresh sources after clock resume")
        super().startup_navigation(deadline)

    def resume(self):
        super().resume()
        for robot in (1,2,3):
            response=self.call(Trigger,f"/net01/tb{robot}/arm",Trigger.Request())
            self.event("network_local_arm",robot=robot,success=response.success,detail=response.message)
            if not response.success:raise RuntimeError("Actual STA guard refused arm: "+str(robot))

    def persist_observer_records(self):
        # Original caller has already stopped controller, bag and launch here.
        if gateway is not None:original.end_process(gateway,self,"network_gateway")
        (self.directory/"network-gateway-exit.json").write_text(json.dumps(dict(
            native_exit=None if gateway is None else gateway.poll(),
            phase="after_original_stop_and_owned_launch_cleanup_attempts")))
        (self.directory/"received-controller-records.json").write_text(json.dumps(self.received_controller))
        super().persist_observer_records()


observer=None
gateway=None


def received_controller_end(directory,position):
    rows=observer.received_controller
    while position<len(rows):
        row=rows[position];position+=1
        if row.get("kind")=="rl_halt_requested":return row["reason"],position
    return None,position


def popen(command,*args,**kwargs):
    global gateway
    command=list(command)
    if command[:2]==["ros2","launch"]:
        if command[2]!=str(FROZEN/"gz01/scene_launch.py"):
            raise RuntimeError("Unexpected launch source at external adapter")
        command[2]=str(HERE/"net_scene_launch.py")
        log=(observer.directory/"network-gateway.log").open("x")
        gateway=subprocess.Popen([sys.executable,"-B",str(HERE/"gateway.py"),
            "--mode",os.environ["NET01_MODE"],"--socket",os.environ["NET01_SOCKET"],
            "--session-id",os.environ["NET01_SESSION_ID"],"--directory",str(observer.directory)],
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        original.record_process(observer.directory,"network_gateway",gateway.pid)
    elif len(command)>2 and command[:2]==["python3","-B"] and command[2]==str(FROZEN/"gz01/headquarters.py"):
        kwargs["env"]=dict(os.environ,ROS_DOMAIN_ID="91")
    return subprocess.Popen(command,*args,**kwargs)


def main():
    # Frozen validate_ready/stop/policy source remain intact. This supplies only
    # the explicit transport composition and the received halt-input adapter.
    original.Observer=NetworkObserver
    original.controller_end=received_controller_end
    original.subprocess=SimpleNamespace(Popen=popen,run=subprocess.run,STDOUT=subprocess.STDOUT,
        TimeoutExpired=subprocess.TimeoutExpired)
    return original.main()


if __name__=="__main__":raise SystemExit(main())
