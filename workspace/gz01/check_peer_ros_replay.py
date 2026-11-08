"""Isolated real-ROS replay of sealed inputs; whitelist excludes all control."""
import json
import os
os.environ['ROS_DOMAIN_ID']='70'
import signal
import subprocess
import threading
import time
import types
from pathlib import Path

import numpy as np
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, qos_profile_sensor_data
from nav_msgs.msg import OccupancyGrid
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String

from peer_keepout import PeerKeepout, peer_mask, ROBOTS
from run_case import Observer

ROOT=Path('/mnt')
OUTPUT=ROOT/'evidence/peer-ros-replay-02'
WHITELIST=['/clock',*(f'/{r}/{t}' for r in ROBOTS for t in ('odom','tf','tf_static'))]


class Consumer(Node):
    def __init__(self, arm_after, failure_sim):
        super().__init__('peer_health_replay_consumer')
        self.sim=None;self.peer_guard=True;self.peer_state=None;self.peer_received=0.
        self.diagnostic_deadline_sim=None;self.diagnostic_budget_exhausted=False
        self.arm_after=arm_after;self.failure_sim=failure_sim;self.negative=False
        self.normal_errors=[];self.negative_errors=[];self.snapshots=[];self.grids={};self.seen_states={}
        self.subs=[self.create_subscription(Clock,'/clock',self.clock,qos_profile_sensor_data),
                   self.create_subscription(String,'/peer_keepout_state',self.health,10)]
        qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.subs += [self.create_subscription(OccupancyGrid,f'/{r}/peer_keepout_mask',
                      lambda m,r=r:self.mask(m,r),qos) for r in ROBOTS]

    def clock(self,msg):
        Observer.clock(self,msg);self.check()

    def health(self,msg):
        Observer.peer_health(self,msg)
        if abs(self.peer_state['generated_sim']-self.failure_sim)<=.35:
            state=self.peer_state.copy();state['consumer_sim']=self.sim
            state['consumer_received_steady']=self.peer_received
            elapsed=self.sim-state['generated_sim']
            state['consumer_odom_ages']={r:v['source']+elapsed for r,v in state['ages'].items()}
            state['consumer_correction_ages']={r:v['correction']+elapsed for r,v in state['ages'].items()}
            self.snapshots.append(state)
            self.seen_states[round(state['generated_sim']*1e9)]=state
        self.check()

    def mask(self,msg,robot):
        stamp=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9
        if abs(stamp-self.failure_sim)<=.35:
            self.grids[(robot,round(stamp*1e9))]=np.asarray(msg.data,dtype=np.int8).reshape(msg.info.height,msg.info.width).copy()

    def check(self):
        if self.sim is None or self.sim<self.arm_after:return
        error=Observer.peer_error(self)
        if error:
            row=dict(sim=self.sim,error=error,negative=self.negative)
            (self.negative_errors if self.negative else self.normal_errors).append(row)


def run(case_name, output_name):
    case=ROOT/'runs'/case_name;out=OUTPUT/output_name;out.mkdir(parents=True,exist_ok=False)
    raw=json.loads((case/'result.json').read_text())
    events=[json.loads(s) for s in (case/'events.jsonl').read_text().splitlines()]
    failure=next(r['sim'] for r in events if r['kind']=='error')
    rclpy.init(args=['--ros-args','-p','use_sim_time:=true'])
    producer=PeerKeepout(json.loads((ROOT/'inputs/scenes/final-open-ring.json').read_text()),out)
    consumer=Consumer(raw['autonomy_start_sim'],failure)
    executor=MultiThreadedExecutor(num_threads=3);executor.add_node(producer);executor.add_node(consumer)
    thread=threading.Thread(target=executor.spin,daemon=True);thread.start()
    qos={f'/{r}/tf_static':dict(history='keep_last',depth=100,reliability='reliable',durability='transient_local') for r in ROBOTS}
    import yaml
    override=out/'qos.yaml';override.write_text(yaml.safe_dump(qos))
    command=['ros2','bag','play',str(case/'bag'),'--rate','1.0','--delay','1.0','--disable-keyboard-controls',
             '--qos-profile-overrides-path',str(override),'--topics',*WHITELIST]
    log=(out/'bag-play.log').open('x');process=None
    try:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
        process.wait(timeout=80)
        assert process.returncode==0,process.returncode
        consumer.negative=True
        # Source inputs are now genuinely absent. Advance only this isolated
        # domain's clock; no robot command or Action publisher exists here.
        clock_pub=consumer.create_publisher(Clock,'/clock',10)
        last=consumer.sim
        for i in range(1,13):
            val=last+i*.1;msg=Clock();ns=round(val*1e9);msg.clock.sec=ns//1_000_000_000;msg.clock.nanosec=ns%1_000_000_000
            clock_pub.publish(msg);time.sleep(.1)
        matches=[]
        for stamp,state in consumer.seen_states.items():
            for robot in ROBOTS:
                key=(robot,stamp)
                assert key in consumer.grids,(robot,stamp,'mask missing')
                expected=peer_mask(robot,state['poses'],state['origins'][robot]) if state['ready'] else np.full_like(consumer.grids[key],100)
                assert np.array_equal(expected,consumer.grids[key]),(robot,stamp,'mask/state mismatch')
                matches.append(dict(robot=robot,stamp_ns=stamp,sequence=state['sequence']))
        result=dict(case=case_name,domain=70,whitelist=WHITELIST,bag_play_command=command,
            real_producer='PeerKeepout',consumer='actual Observer clock/peer_health/peer_error; no Observer constructor',
            normal_errors=consumer.normal_errors,negative_errors=consumer.negative_errors,
            failure_window_snapshots=consumer.snapshots,matching_masks=matches,
            input_stop_detected=bool(consumer.negative_errors),Gazebo=0,Nav2_actions=0,cmd_publishers=0,NN=0,
            scope='Real ROS/DDS/TF2 playback at stored receipt timing, not Gazebo/SLAM/Nav2 load or exact historical executor-order attribution')
        result['passed']=not result['normal_errors'] and result['input_stop_detected'] and bool(matches)
        (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('failure_window_snapshots','negative_errors','matching_masks')},indent=2),flush=True)
        return result['passed']
    finally:
        if process is not None and process.poll() is None:process.send_signal(signal.SIGINT);process.wait(timeout=10)
        executor.shutdown();thread.join(timeout=3);producer.destroy_node();consumer.destroy_node();rclpy.shutdown();log.close()


def main():
    OUTPUT.mkdir(exist_ok=False)
    passed=[]
    for case,name in [('peer-open-ring-traditional-01','slot3'),('peer-open-ring-traditional-02','slot4')]:passed.append(run(case,name))
    (OUTPUT/'summary.json').write_text(json.dumps(dict(passed=all(passed),case_results=passed,ROS_DOMAIN_ID=70,Gazebo=0,NN=0)))
    if not all(passed):raise SystemExit(1)


if __name__=='__main__':main()
