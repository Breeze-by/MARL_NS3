"""One <=20wall isolated continuous DDS diagnostic, never Gazebo/Policy/Nav2.

Actual Gateway A/BoundPeer/native clock model; synthetic continuous R sources.
The reserved C91/R92 domains must have no other NET owner before invocation.
"""
import argparse
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parents[1]


def source(directory,feedback_hz):
    import rclpy
    from rclpy.clock import Clock,ClockType
    from rclpy.node import Node
    from rclpy.qos import QoSProfile,DurabilityPolicy,qos_profile_sensor_data
    from rclpy.signals import SignalHandlerOptions
    from rosgraph_msgs.msg import Clock as ClockMessage
    from geometry_msgs.msg import TransformStamped,Twist
    from tf2_msgs.msg import TFMessage
    from nav_msgs.msg import Odometry,OccupancyGrid
    from std_msgs.msg import String
    from array import array
    rclpy.init(domain_id=92,signal_handler_options=SignalHandlerOptions.NO)
    node=Node('net01_synthetic_continuous_source')
    steady=Clock(clock_type=ClockType.STEADY_TIME)
    records=[];timers=[];publishers=[];services=[];clock_ns=100_000_000
    cp=node.create_publisher(ClockMessage,'/clock',qos_profile_sensor_data)
    def stamp(header,value):header.stamp.sec=value//1_000_000_000;header.stamp.nanosec=value%1_000_000_000
    def emit(pub,message,robot,kind,header=None):
        row=dict(robot=robot,kind=kind,source_header_ns=header,
            before_monotonic_ns=time.monotonic_ns())
        pub.publish(message);row['after_monotonic_ns']=time.monotonic_ns();records.append(row)
    def publish_clock():
        nonlocal clock_ns
        m=ClockMessage();m.clock.sec=clock_ns//1_000_000_000;m.clock.nanosec=clock_ns%1_000_000_000
        emit(cp,m,0,'synthetic_clock',clock_ns);clock_ns+=100_000_000
    publish_clock()
    timers.append(node.create_timer(.1,publish_clock,clock=steady))
    qualified=False
    def state(message):
        nonlocal qualified
        data=json.loads(message.data)
        qualified=data['connected'] and data['anchor'] is not None and data['failure'] is None
    qualification=node.create_subscription(String,'/net01/gateway_state',state,
        QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    until=time.monotonic()+2
    while not qualified and time.monotonic()<until:rclpy.spin_once(node,timeout_sec=.001)
    if not qualified:raise RuntimeError('Real gateway did not establish clock anchor before synthetic business')
    scene=json.loads((HERE.parent/'inputs/scenes/regression-corridor-common-6201-dwb-v1.json').read_text())
    latched=QoSProfile(depth=100,durability=DurabilityPolicy.TRANSIENT_LOCAL)
    for robot in (1,2,3):
        prefix=f'/tb{robot}'
        # Distinct DataWriters on each /tf retain the original aggregation issue.
        tf_pubs=[node.create_publisher(TFMessage,prefix+'/tf',100) for _ in range(3)]
        odom_pub=node.create_publisher(Odometry,prefix+'/odom',10)
        zero_pub=node.create_publisher(Twist,prefix+'/cmd_vel',4)
        static_pub=node.create_publisher(TFMessage,prefix+'/tf_static',latched)
        publishers.extend([*tf_pubs,odom_pub,zero_pub,static_pub])
        t=TransformStamped();t.header.frame_id='merge_map';t.child_frame_id='map';t.transform.rotation.w=1.
        t.transform.translation.x=scene['robots'][robot-1]['x'];t.transform.translation.y=scene['robots'][robot-1]['y']
        emit(static_pub,TFMessage(transforms=[t]),robot,'static',0)
        def transform(pub,frame,child,robot=robot,future=0):
            t=TransformStamped();t.header.frame_id=frame;t.child_frame_id=child;t.transform.rotation.w=1.
            value=clock_ns-100_000_000+future;stamp(t.header,value)
            emit(pub,TFMessage(transforms=[t]),robot,frame+'->'+child,value)
        timers.append(node.create_timer(.02,lambda p=tf_pubs[0],r=robot:
            transform(p,'map','odom',r,200_000_000),clock=steady))
        def odom(p=odom_pub,tfp=tf_pubs[1],robot=robot):
            m=Odometry();m.header.frame_id='odom';m.child_frame_id='base_footprint';m.pose.pose.orientation.w=1.
            value=clock_ns-100_000_000;stamp(m.header,value)
            emit(p,m,robot,'odom',value);transform(tfp,'odom','base_footprint',robot)
        timers.append(node.create_timer(1/30,odom,clock=steady))
        timers.append(node.create_timer(.05,lambda p=tf_pubs[2],r=robot:
            transform(p,'base_link','wheel_left_link',r),clock=steady))
        timers.append(node.create_timer(.05,lambda p=zero_pub,r=robot:emit(p,Twist(),r,'exact_zero_cmd'),clock=steady))
        # Original map/costmap input sizes, but synthetic and never used by policy.
        mp=node.create_publisher(OccupancyGrid,prefix+'/map',QoSProfile(depth=10,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        lp=node.create_publisher(OccupancyGrid,prefix+'/local_costmap/costmap',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        publishers.extend([mp,lp])
        def grid(pub,width,height,kind,robot=robot):
            m=OccupancyGrid();m.header.frame_id='map';stamp(m.header,clock_ns-100_000_000)
            m.info.resolution=.05;m.info.width=width;m.info.height=height;m.info.origin.orientation.w=1.
            m.data=array('b',[0])*(width*height)
            emit(pub,m,robot,kind,clock_ns-100_000_000)
        grid(mp,250,220,'synthetic_map')
        timers.append(node.create_timer(5.,lambda p=mp,r=robot:grid(p,250,220,'synthetic_map',r),clock=steady))
        timers.append(node.create_timer(.5,lambda p=lp,r=robot:grid(p,60,60,'synthetic_costmap',r),clock=steady))
        if feedback_hz:
            from nav2_msgs.action import NavigateToPose
            from action_msgs.msg import GoalStatusArray
            from rclpy.qos import qos_profile_action_status_default
            from action_wire import SERVICES
            action=prefix+'/navigate_to_pose/_action/'
            def no_request(request,response):
                raise RuntimeError('Continuous no-goal fixture received an unexpected business request')
            for _,typ,suffix in SERVICES:services.append(node.create_service(typ,action+suffix,no_request))
            fp=node.create_publisher(NavigateToPose.Impl.FeedbackMessage,action+'feedback',10)
            sp=node.create_publisher(GoalStatusArray,action+'status',qos_profile_action_status_default)
            publishers.extend([fp,sp])
            def feedback(pub=fp,robot=robot):
                m=NavigateToPose.Impl.FeedbackMessage();m.goal_id.uuid=[robot]*16
                m.feedback.current_pose.header.frame_id='map'
                value=clock_ns-100_000_000;stamp(m.feedback.current_pose.header,value)
                m.feedback.current_pose.pose.orientation.w=1.;m.feedback.distance_remaining=2.
                emit(pub,m,robot,'synthetic_action_feedback',value)
            emit(sp,GoalStatusArray(),robot,'synthetic_action_status')
            timers.append(node.create_timer(1/feedback_hz,feedback,clock=steady))
            timers.append(node.create_timer(1.,lambda p=sp,r=robot:emit(p,GoalStatusArray(),r,'synthetic_action_status'),clock=steady))
    start=time.monotonic()
    try:
        while time.monotonic()-start<8:rclpy.spin_once(node,timeout_sec=.001)
    finally:
        node.destroy_node();rclpy.shutdown()
        (directory/'source.json').write_text(json.dumps(dict(scope='SYNTHETIC continuous isolated DDS; no GZ/Nav2/NN/nonzero motion',
            requested_window_wall_s=8,feedback_hz=feedback_hz,actual_window_wall_s=time.monotonic()-start,records=records)))


def stop_check(stop_file,records):
    begin=time.monotonic_ns();cpu=time.thread_time_ns()
    stopped=stop_file.exists()
    records.append(dict(wall_ns=time.monotonic_ns()-begin,cpu_ns=time.thread_time_ns()-cpu))
    return stopped


def peer(directory,stop_file):
    import rclpy
    from rclpy.signals import SignalHandlerOptions
    sys.path.insert(0,str(HERE))
    from bound_peer import BoundPeer
    rclpy.init(domain_id=91,args=['--ros-args','-p','use_sim_time:=true'],signal_handler_options=SignalHandlerOptions.NO)
    scene=json.loads((HERE.parent/'inputs/scenes/regression-corridor-common-6201-dwb-v1.json').read_text())
    node=BoundPeer(scene,directory,session_id=2026110912)
    checks=[];next_check=0
    try:
        while True:
            if time.monotonic()>=next_check:
                if stop_check(stop_file,checks):break
                next_check=time.monotonic()+.05
            rclpy.spin_once(node,timeout_sec=.01)
    finally:
        node.persist_records();node.destroy_node();rclpy.shutdown()
        (directory/'fixture-stop-overhead.json').write_text(json.dumps(checks))


def gateway(directory,stop_file,dispatch_profile):
    sys.path.insert(0,str(HERE))
    from gateway import Gateway
    node=Gateway('A',directory.parent/'wire.sock',directory,2026110912,
        dispatch_profile=dispatch_profile)
    checks=[];next_check=0
    try:
        while True:
            if time.monotonic()>=next_check:
                if stop_check(stop_file,checks):break
                next_check=time.monotonic()+.05
            try:node.poll()
            except Exception as error:node.fail(repr(error))
    finally:clean=node.close()
    (directory/'fixture-stop-overhead.json').write_text(json.dumps(checks))
    return 0 if clean else 1


def host(name,feedback_hz,dispatch_profile):
    repo=HERE.parent;phase=repo.parent
    base=repo/'runs'/name;base.mkdir(exist_ok=False)
    for role_name in ('source','peer','gateway'):(base/role_name).mkdir()
    (base/'scope.json').write_text(json.dumps(dict(scope='Synthetic-clock continuous DDS diagnostic; NOT GZ TIME/NET safety',
        hard_wall_s=20,source_wall_s=8,feedback_hz=feedback_hz,dispatch_profile=dispatch_profile,domains=dict(C=91,R=92),mode='A direct',Gazebo=0,Nav2=0,ActionServer=0,NN=0)))
    start=time.monotonic();deadline=start+19.5;processes={};logs=[];error=None
    def launch(role,args,pipe=False):
        log=(base/(role+'.stderr.txt')).open('x');logs.append(log)
        out=subprocess.PIPE if pipe else (base/(role+'.stdout.txt')).open('x')
        if not pipe:logs.append(out)
        p=subprocess.Popen(args,stdout=out,stderr=log,start_new_session=True,text=True)
        processes[role]=p;return p
    wrapper=['bash',str(HERE/'ros-python.sh')]
    sub='/mnt/net01/followup01/continuous_dds.py'
    socket=base/'wire.sock'
    try:
        hub=launch('hub',[sys.executable,'-B',str(HERE/'tools/packet_hub.py'),'--socket',str(socket),
            '--native',str(phase/'build/network-full-payload/net01-payload'),'--output',str(base/'hub'),
            '--profile','B','--wall','19','--clock-source','gazebo'],pipe=True)
        readable,_,_=select.select([hub.stdout],[],[],min(5,deadline-time.monotonic()))
        if not readable or hub.stdout.readline().strip()!='IPC_LISTENING '+str(socket):raise RuntimeError('Native IPC startup failed')
        stop='/mnt/runs/'+name+'/STOP'
        launch('peer',wrapper+[sub,'--role','peer','--directory','/mnt/runs/'+name+'/peer','--stop-file',stop])
        launch('gateway',wrapper+[sub,'--role','gateway','--directory','/mnt/runs/'+name+'/gateway','--stop-file',stop]+(['--dispatch-profile'] if dispatch_profile else []))
        src=launch('source',wrapper+[sub,'--role','source','--directory','/mnt/runs/'+name+'/source','--feedback-hz',str(feedback_hz)])
        src.wait(timeout=max(.01,deadline-time.monotonic()-3))
    except BaseException as exc:error=repr(exc)
    finally:
        (base/'STOP').write_text('fixture owned-resource stop only; no business data')
        for role in ('source','peer','gateway','hub'):
            p=processes.get(role)
            if p is None or p.poll() is not None:continue
            try:p.wait(timeout=max(.01,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        result=dict(scope='One continuous synthetic-clock DDS diagnostic; not Gazebo/real-clock or motion safety',
            error=error,wall_s=time.monotonic()-start,hard_wall_s=20,
            exits={role:p.returncode for role,p in processes.items()},Gazebo=0,NN=0,
            wrapper_pids={role:p.pid for role,p in processes.items()},
            stop_control='fixture stop-file polled at most20Hz; exact overhead saved, not production behavior')
        (base/'process-exit.json').write_text(json.dumps(result,indent=2))
        for log in logs:log.close()
    print(json.dumps(result),flush=True)
    return 0 if error is None and all(p.returncode==0 for p in processes.values()) else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--role',choices=['host','source','peer','gateway'],default='host')
    parser.add_argument('--directory',type=Path)
    parser.add_argument('--name',default='continuous-dds-02');parser.add_argument('--stop-file',type=Path)
    parser.add_argument('--feedback-hz',type=int,default=0)
    parser.add_argument('--dispatch-profile',action='store_true')
    a=parser.parse_args()
    raise SystemExit(host(a.name,a.feedback_hz,a.dispatch_profile) if a.role=='host' else source(a.directory,a.feedback_hz) if a.role=='source' else
        gateway(a.directory,a.stop_file,a.dispatch_profile) if a.role=='gateway' else peer(a.directory,a.stop_file))
