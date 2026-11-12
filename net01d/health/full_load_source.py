"""One robot's no-motion P5 source and real controlled ActionServer, domain92.

New fixture observations use stationary encoder/TF values and historical Grid
content templates. Not SLAM/Nav2 or refreshed historical measurements. Observation
supply stops after active-wall; local services keep spinning until final STOP.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO),str(REPO/'net01')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--robot',type=int,choices=(1,2,3),required=True)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--stop-file',type=Path,required=True)
    parser.add_argument('--session-id',type=int,required=True)
    parser.add_argument('--payloads',type=Path,required=True)
    parser.add_argument('--active-wall',type=float,default=32.)
    parser.add_argument('--supply-stop-file',type=Path)
    parser.add_argument('--dds-source-trace',action='store_true')
    args = parser.parse_args()
    import rclpy
    from rclpy.clock import Clock,ClockType
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from rclpy.qos import QoSProfile,DurabilityPolicy,qos_profile_sensor_data
    from rclpy.serialization import deserialize_message
    from rclpy.signals import SignalHandlerOptions
    from geometry_msgs.msg import TransformStamped,Twist
    from tf2_msgs.msg import TFMessage
    from nav_msgs.msg import Odometry,OccupancyGrid
    from nav2_msgs.srv import ManageLifecycleNodes
    from rosgraph_msgs.msg import Clock as ClockMessage
    from std_msgs.msg import String
    from std_srvs.srv import Trigger
    from check_action_wire import ControlledServer
    from followup04.frozen_source_clock import FrozenSourceClock,wheel_message

    args.directory.mkdir(parents=True,exist_ok=True)
    manifest = json.loads((args.payloads/'manifest.json').read_text())
    templates = {}
    template_identity = {}
    for kind in ('map','costmap'):
        meta = manifest['templates'][f'{args.robot}:{kind}']
        grid = deserialize_message((args.payloads/meta['file']).read_bytes(),OccupancyGrid)
        templates[kind] = grid
        template_identity[kind] = dict(meta,original_header=dict(frame_id=grid.header.frame_id,
            sec=grid.header.stamp.sec,nanosec=grid.header.stamp.nanosec),
            original_map_load_time=dict(sec=grid.info.map_load_time.sec,nanosec=grid.info.map_load_time.nanosec),
            shape=[grid.info.width,grid.info.height],resolution=grid.info.resolution,
            changed_fields=['header.stamp','info.map_load_time'],
            unchanged='All content cells, origin, dimensions, resolution, frame and other Grid fields')
    rclpy.init(domain_id=92,signal_handler_options=SignalHandlerOptions.NO)
    node = Node(f'net01d_full_source_tb{args.robot}',parameter_overrides=[Parameter('use_sim_time',value=True)])
    steady = Clock(clock_type=ClockType.STEADY_TIME)
    robot = args.robot;prefix = f'/tb{robot}';clock = FrozenSourceClock()
    rows = [];pauses = [];zeros = [];status = None;active_start = None
    quiet = False;arm_future = None;arm_response = None;error = None
    status_revision=0;arm_rejected_revision=-1
    supply_end_wall=None;active_start_sim_ns=None;supply_end_sim_ns=None
    feedback_publish_calls=0
    tf_ordinals=Counter();tf_matched={}
    def record(kind,**fields):
        rows.append(dict(kind=kind,monotonic_ns=time.monotonic_ns(),
            node_sim_ns=node.get_clock().now().nanoseconds,**fields))
    def emit(pub,message,kind,stamp=None):
        if active_start is None or quiet:
            return
        before = time.monotonic_ns()
        diagnostic=None
        if args.dds_source_trace and kind in ('map->odom','odom->base_footprint','both_wheel_TF'):
            tf_ordinals[kind]+=1
            matched=pub.get_subscription_count()
            diagnostic=dict(writer_kind=kind,publication_ordinal=tf_ordinals[kind],
                matched_readers=matched,before_realtime_ns=time.time_ns(),
                before_realtime_mono_after_ns=time.monotonic_ns())
            if tf_matched.get(kind)!=matched:
                tf_matched[kind]=matched
                record('tf_matched_readers_changed',writer_kind=kind,matched_readers=matched,
                    publication_ordinal=tf_ordinals[kind])
        pub.publish(message)
        after=time.monotonic_ns()
        if diagnostic is not None:
            diagnostic.update(after_realtime_ns=time.time_ns(),after_realtime_mono_after_ns=time.monotonic_ns())
        offset={'fixture_odom':2,'fixture_static':4,'exact_zero_cmd':6,
            'historical_content_fixture_map':1,'historical_content_fixture_costmap':5}.get(kind,3)
        row=dict(kind=kind,flow=robot*20+offset,source_stamp_ns=stamp,before_monotonic_ns=before,
            after_monotonic_ns=after,node_sim_ns=node.get_clock().now().nanoseconds)
        if diagnostic is not None:row['dds_source_trace']=diagnostic
        rows.append(row)
    def stamp(header,value):
        header.stamp.sec,header.stamp.nanosec = divmod(value,1_000_000_000)
    tf = [node.create_publisher(TFMessage,prefix+'/tf',100) for _ in range(3)]
    odom_pub = node.create_publisher(Odometry,prefix+'/odom',10)
    zero_pub = node.create_publisher(Twist,prefix+'/cmd_vel',4)
    static_pub = node.create_publisher(TFMessage,prefix+'/tf_static',
        QoSProfile(depth=100,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    maps = {kind:node.create_publisher(OccupancyGrid,prefix+('/map' if kind=='map' else '/local_costmap/costmap'),
        QoSProfile(depth=10 if kind=='map' else 1,durability=DurabilityPolicy.TRANSIENT_LOCAL)) for kind in templates}
    def transform(pub,frame,child,value):
        message = TransformStamped();message.header.frame_id=frame;message.child_frame_id=child
        stamp(message.header,value);message.transform.rotation.w=1.
        emit(pub,TFMessage(transforms=[message]),frame+'->'+child,value)
    def actual_clock(message):
        value = message.clock.sec*1_000_000_000+message.clock.nanosec
        due = clock.advance(value)
        if 'odom' in due:
            message = Odometry();message.header.frame_id='odom';message.child_frame_id='base_footprint'
            stamp(message.header,value);message.pose.pose.orientation.w=1.
            emit(odom_pub,message,'fixture_odom',value)
            transform(tf[1],'odom','base_footprint',value)
        if 'wheel' in due:
            emit(tf[2],wheel_message(value),'both_wheel_TF',value)
    node.create_subscription(ClockMessage,'/clock',actual_clock,qos_profile_sensor_data)
    def gateway_state(message):
        nonlocal status,status_revision
        status = json.loads(message.data)
        status_revision+=1
    node.create_subscription(String,'/net01/gateway_state',gateway_state,
        QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    server = ControlledServer(node,robot)
    node.destroy_timer(server.timer)
    def server_tick():
        nonlocal feedback_publish_calls
        count=len(server.executing)
        server.tick()
        feedback_publish_calls+=count
    server.timer = node.create_timer(.01,server_tick,clock=steady)
    # Existing ControlledServer emits complete fixed fixture feedback while its
    # real handle executes. Its goal pose is a fixture pose, never robot telemetry.
    arm = node.create_client(Trigger,f'/net01/tb{robot}/arm')
    def pause(request,response):
        pauses.append(dict(command=request.command,monotonic_ns=time.monotonic_ns()))
        response.success = request.command==ManageLifecycleNodes.Request.PAUSE
        return response
    node.create_service(ManageLifecycleNodes,prefix+'/lifecycle_manager_navigation/manage_nodes',pause)
    node.create_subscription(Twist,prefix+'/cmd_vel',lambda message:zeros.append(dict(
        monotonic_ns=time.monotonic_ns(),is_exact_zero=message==Twist())),10)
    def merged(message):
        record('actual_R_merge_map_consumed',flow=89,header_stamp_ns=message.header.stamp.sec*1_000_000_000+message.header.stamp.nanosec,
            frame_id=message.header.frame_id,width=message.info.width,height=message.info.height,data_cells=len(message.data))
    node.create_subscription(OccupancyGrid,'/merge_map',merged,
        QoSProfile(depth=10,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    node.create_subscription(String,'/net01/controller_records',
        lambda message:record('actual_R_controller_journal_consumed',flow=95,data=message.data),100)
    def grid(kind):
        message = templates[kind]
        value = clock.scan_header_ns if kind=='map' else node.get_clock().now().nanoseconds
        stamp(message.header,value)
        # This is a newly loaded fixture map, not a renamed historical load time.
        if active_start is not None:
            message.info.map_load_time = fixture_load_time
        emit(maps[kind],message,'historical_content_fixture_'+kind,value)
    node.create_timer(.02,lambda:transform(tf[0],'map','odom',clock.scan_header_ns+200_000_000)
        if clock.scan_header_ns is not None else None,clock=steady)
    node.create_timer(.05,lambda:emit(zero_pub,Twist(),'exact_zero_cmd'),clock=steady)
    node.create_timer(5.,lambda:grid('map') if active_start is not None else None,clock=steady)
    def costmap_poll():
        if active_start is not None and not quiet and clock.costmap_due(robot,node.get_clock().now().nanoseconds):
            grid('costmap')
    node.create_timer(.2,costmap_poll,clock=steady)
    scene = json.loads((REPO/'inputs/scenes/regression-corridor-common-6201-dwb-v1.json').read_text())
    started = time.monotonic()
    fixture_load_time = None
    try:
        print(f'FULL_LOAD_R_READY tb{robot}',flush=True)
        while not args.stop_file.exists():
            if time.monotonic()-started>60:
                raise TimeoutError('P5 R source/service60wall hard bound')
            rclpy.spin_once(node,timeout_sec=.001)
            if active_start is None:
                if not (status and status['session_id']==args.session_id and status['connected'] and status['anchor'] is not None and clock.sim_ns is not None):
                    continue
                active_start = time.monotonic();fixture_load_time=node.get_clock().now().to_msg()
                active_start_sim_ns=node.get_clock().now().nanoseconds
                record('fixture_observations_active',active_wall=args.active_wall,
                    source_ticks=dict(clock.ticks),skipped_configured_ticks=dict(clock.skipped_configured_ticks),
                    clock_origin_ns=clock.origin_ns,scan_header_ns=clock.scan_header_ns)
                t=TransformStamped();t.header.frame_id='merge_map';t.child_frame_id='map';t.transform.rotation.w=1.
                t.transform.translation.x=scene['robots'][robot-1]['x'];t.transform.translation.y=scene['robots'][robot-1]['y']
                emit(static_pub,TFMessage(transforms=[t]),'fixture_static',0);grid('map')
            stop_supply = (args.supply_stop_file.exists() if args.supply_stop_file is not None
                else time.monotonic()-active_start>=args.active_wall)
            if not quiet and stop_supply:
                quiet=True
                supply_end_wall=time.monotonic();supply_end_sim_ns=node.get_clock().now().nanoseconds
                record('observation_supply_stopped_services_continue',
                    source_ticks=dict(clock.ticks),skipped_configured_ticks=dict(clock.skipped_configured_ticks),
                    clock_origin_ns=clock.origin_ns,scan_header_ns=clock.scan_header_ns)
                with (args.directory/'OBSERVATIONS_STOPPED.json').open('x') as stream:
                    json.dump(rows[-1],stream)
            if (not quiet and arm_future is None and status_revision>arm_rejected_revision
                    and status['guards'][str(robot)]['reason'] is None
                    and status['guards'][str(robot)]['fault'] is None and arm.service_is_ready()):
                arm_future=arm.call_async(Trigger.Request());arm_response=None
                record('actual_local_arm_request',status_revision=status_revision)
            if arm_future is not None and arm_future.done() and arm_response is None:
                response=arm_future.result();arm_response=dict(success=response.success,message=response.message)
                record('actual_local_arm_response',status_revision=status_revision,**arm_response)
                if not response.success and json.loads(response.message)['fault'] is None:
                    # A rejected bootstrap ARM may race the next status. Wait for
                    # a new healthy status before asking the unchanged Guard again.
                    arm_rejected_revision=status_revision;arm_future=None
            # Long real GetResult waits under the full load; release after26wall
            # of observation supply, leaving the original six-second tail budget.
            if robot!=3 and time.monotonic()-active_start>=args.active_wall-6:
                server.release.update(server.executing)
    except BaseException as exc:
        error=repr(exc);raise
    finally:
        if active_start is not None and supply_end_wall is None:
            supply_end_wall=time.monotonic();supply_end_sim_ns=node.get_clock().now().nanoseconds
            record('observation_supply_ends_at_final_STOP',source_ticks=dict(clock.ticks),
                skipped_configured_ticks=dict(clock.skipped_configured_ticks),
                clock_origin_ns=clock.origin_ns,scan_header_ns=clock.scan_header_ns)
        data=dict(scope='P5 stationary synthetic observations with complete historical Grid content; real controlled ActionServer, not Nav2/SLAM',
            robot=robot,session_id=args.session_id,active_wall_requested=args.active_wall,error=error,
            template_identity=template_identity,records=rows,arm_response=arm_response,
            final_gateway_status=status,accepted_Goal_CDR=server.accepted,cancelled=server.cancelled,
            still_executing=list(server.executing),pause_requests=pauses,zero_messages=zeros,
            source_ticks=clock.ticks,skipped_configured_ticks=clock.skipped_configured_ticks,
            active_supply_wall_s=None if active_start is None else supply_end_wall-active_start,
            active_supply_begin_sim_ns=active_start_sim_ns,active_supply_end_sim_ns=supply_end_sim_ns,
            emitted_counts=[dict(flow=flow,kind=kind,count=count) for (flow,kind),count in
                sorted(Counter((r['flow'],r['kind']) for r in rows if 'before_monotonic_ns' in r).items())],
            feedback_publisher_calls_after_successful_tick=feedback_publish_calls,
            zero_spy_scope='R spy sees source and Guardian zero writers; receipt alone does not identify Guardian or physical driver consumption',
            dds_source_trace_enabled=args.dds_source_trace,
            feedback_contract='Existing ControlledServer full feedback fields at100wall Hz only while actual goal handle executes')
        with (args.directory/'full-source.json').open('x') as stream:
            json.dump(data,stream);stream.write('\n')
        server.close();node.destroy_node();rclpy.try_shutdown()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
