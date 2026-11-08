"""ROS adapter for the shared BASE-02 allocation contract. Nav2 owns motion."""
import json
import hashlib
import math
import os
from pathlib import Path
import threading
import time
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.time import Time
from rclpy.qos import QoSProfile, DurabilityPolicy
from rclpy.executors import ExternalShutdownException
from nav_msgs.msg import OccupancyGrid, Odometry
from geometry_msgs.msg import PointStamped, Twist
from nav2_msgs.action import NavigateToPose
from tf2_ros import Buffer, TransformException
from tf2_msgs.msg import TFMessage
from tf2_geometry_msgs import do_transform_point
from .allocation import Allocator, policy_for
from .evaluation import Evaluator


class HeadquartersControl(Node):
    def __init__(self, num_robots):
        super().__init__('headquarters_control')
        mode=self.declare_parameter('allocator','traditional').value
        # Offline rl/test adapters are usable; untrained policies cannot command Gazebo.
        if mode != 'traditional':
            raise ValueError('BASE-02 ROS autonomy only permits traditional; rl/test are offline interfaces')
        self.policy=policy_for(mode)
        self.lock=threading.RLock()
        self.worker_error=None
        self.goal_handles={}
        self.local_maps={}
        self.pose_tf_errors={}
        self.tf={r:Buffer(cache_time=Duration(seconds=15),node=self) for r in (f'tb{i+1}' for i in range(num_robots))}
        self.robot_nav_clients={r:ActionClient(self,NavigateToPose,f'/{r}/navigate_to_pose') for r in self.tf}
        directory=Path(os.environ.get('BASE01_RUN_DIR','/tmp'))
        self.events=(directory/'allocation-events.jsonl').open('x',buffering=1)
        self.evaluator=Evaluator(tuple(self.tf))
        self.allocator=Allocator(tuple(self.tf),self.goal_valid,self.record)
        self.record(dict(kind='implementation_identity',sim=self.now(),files={
            name:dict(path=str(Path(__file__).parent/name),sha256=hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest())
            for name in ('control.py','allocation.py','frontier.py','evaluation.py','environment.py')}))
        self.subscriptions_kept=[]
        latched=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        static_qos=QoSProfile(depth=100,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.subscriptions_kept.append(self.create_subscription(OccupancyGrid,'/merge_map',self.map_callback,10))
        for r in self.tf:
            self.subscriptions_kept += [
                self.create_subscription(Odometry,f'/{r}/odom',lambda m,r=r:self.robot_odom_callback(m,r),10),
                self.create_subscription(Twist,f'/{r}/cmd_vel',lambda m,r=r:self.robot_status_control(m,r),4),
                self.create_subscription(OccupancyGrid,f'/{r}/map',lambda m,r=r:self.local_map_callback(m,r),latched),
                self.create_subscription(TFMessage,f'/{r}/tf',lambda m,r=r:self.tf_callback(m,r,False),100),
                self.create_subscription(TFMessage,f'/{r}/tf_static',lambda m,r=r:self.tf_callback(m,r,True),static_qos)]
        for i in range(num_robots):
            threading.Thread(target=self.exploration_worker,args=(i+1,),daemon=True).start()
        self.get_logger().info('BASE-02 traditional allocator initialized; Nav2 execution unchanged.')

    def now(self):
        return self.get_clock().now().nanoseconds*1e-9

    def record(self, event):
        self.events.write(json.dumps(event)+'\n')
        self.evaluator.event(event)

    def tf_callback(self, msg, robot, static):
        with self.lock:
            for transform in msg.transforms:
                if static:self.tf[robot].set_transform_static(transform,robot)
                else:self.tf[robot].set_transform(transform,robot)

    def map_callback(self,msg):
        if msg.header.frame_id!='merge_map':raise ValueError('Expected merge_map frame')
        with self.lock:
            self.allocator.tick(self.now())
            self.allocator.update_map(np.array(msg.data).reshape(msg.info.height,msg.info.width),
                msg.info.resolution,(msg.info.origin.position.x,msg.info.origin.position.y),
                msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9)

    def local_map_callback(self,msg,robot):
        if msg.header.frame_id!='map':raise ValueError('Expected namespaced map frame')
        with self.lock:self.local_maps[robot]=msg

    def nav_goal_in_local_map(self,robot,x,y,planner_bounds=False):
        grid=self.local_maps.get(robot)
        if grid is None:return False
        origin=grid.info.origin; q=origin.orientation
        if not math.isclose(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w,1.,abs_tol=1e-5):return False
        yaw=math.atan2(2*q.w*q.z,1-2*q.z*q.z)
        dx,dy=x-origin.position.x,y-origin.position.y
        if planner_bounds:
            # Navfn worldToMap uses positive std::round, unlike Costmap2D floor.
            mx=math.floor(dx/grid.info.resolution+.5);my=math.floor(dy/grid.info.resolution+.5)
            if dx<0 or dy<0 or not (0<=mx<grid.info.width and 0<=my<grid.info.height):return False
        c=math.floor((math.cos(yaw)*dx+math.sin(yaw)*dy)/grid.info.resolution)
        r=math.floor((-math.sin(yaw)*dx+math.cos(yaw)*dy)/grid.info.resolution)
        return 0<=c<grid.info.width and 0<=r<grid.info.height and grid.data[r*grid.info.width+c]==0

    def local_point(self,robot,target):
        point=PointStamped(); point.header.frame_id='merge_map'; point.point.x,point.point.y=target
        transform=self.tf[robot].lookup_transform('map','merge_map',Time())
        return do_transform_point(point,transform).point,transform.transform.rotation

    def local_navigation_grid(self, robot, shared):
        from .observations import project_local_navigation
        grid=self.local_maps.get(robot)
        if grid is None:return None
        try:stamped_transform=self.tf[robot].lookup_transform('map','merge_map',Time())
        except TransformException:return None
        transform=stamped_transform.transform
        origin=grid.info.origin
        def yaw(q):
            if not math.isclose(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w,1.,abs_tol=1e-5):
                raise ValueError('Invalid local navigation quaternion')
            return math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        projected=project_local_navigation(
            np.asarray(grid.data).reshape(grid.info.height,grid.info.width),grid.info.resolution,
            (origin.position.x,origin.position.y,yaw(origin.orientation)),
            (transform.translation.x,transform.translation.y,yaw(transform.rotation)),shared)
        self.record(dict(kind='local_navigation_grid',sim=self.now(),robot=robot,
            source=f'/{robot}/map',frame=grid.header.frame_id,
            map_stamp=dict(sec=grid.header.stamp.sec,nanosec=grid.header.stamp.nanosec),
            resolution=grid.info.resolution,shape=[grid.info.height,grid.info.width],
            origin=[origin.position.x,origin.position.y,yaw(origin.orientation)],
            tf_target=stamped_transform.header.frame_id,tf_source=stamped_transform.child_frame_id,
            tf_stamp=dict(sec=stamped_transform.header.stamp.sec,nanosec=stamped_transform.header.stamp.nanosec),
            local_from_shared=[transform.translation.x,transform.translation.y,yaw(transform.rotation)],
            shared_version=shared['version'],shared_stamp=shared['stamp'],
            shared_origin=shared['origin'],shared_resolution=shared['resolution'],shared_shape=list(projected.shape)))
        return projected

    def goal_valid(self,robot,x,y):
        try:point,_=self.local_point(robot,(x,y))
        except TransformException:return None
        if robot not in self.local_maps:return None
        return self.nav_goal_in_local_map(robot,point.x,point.y)

    def robot_odom_callback(self,msg,robot):
        point=PointStamped();point.header=msg.header;point.point=msg.pose.pose.position
        with self.lock:
            try:
                transform=self.tf[robot].lookup_transform('merge_map',msg.header.frame_id,Time.from_msg(msg.header.stamp))
                p=do_transform_point(point,transform).point
            except TransformException as error:
                previous=self.pose_tf_errors.get(robot,{})
                self.pose_tf_errors[robot]=dict(count=previous.get('count',0)+1,
                    error=type(error).__name__,message=str(error),sim=self.now(),
                    odom_stamp=msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9)
                # Keep the last exact-stamp success and its original stamp.
                # Allocation still rejects it when the2s freshness budget expires.
                return False
            q=msg.pose.pose.orientation; t=transform.transform.rotation
            yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))+math.atan2(2*(t.w*t.z+t.x*t.y),1-2*(t.y*t.y+t.z*t.z))
            self.allocator.update_robot(robot,(p.x,p.y,yaw),msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9,
                (msg.twist.twist.linear.x,msg.twist.twist.linear.y,msg.twist.twist.angular.z))
            self.record(dict(kind='pose',robot=robot,position=(p.x,p.y),sim=self.now(),source='odom + TF'))
            return True

    def robot_status_control(self,msg,robot):
        # Observation only. This adapter has no cmd_vel publisher.
        pass

    def exploration_worker(self,number):
        try:self.start_exploration(number)
        except Exception as error:
            self.worker_error=f'tb{number}: {type(error).__name__}: {error}'
            self.get_logger().fatal(self.worker_error)
            self.context.try_shutdown()

    def start_exploration(self,number):
        robot=f'tb{number}'
        while rclpy.ok():
            proposals={}
            with self.lock:
                self.allocator.tick(self.now())
                state=self.allocator.robots[robot]
                if self.allocator.map is not None and state.pose is not None and self.now()-state.stamp<=2. and state.state=='idle':
                    observation=self.allocator.get_observation(trigger=robot)
                    proposals,_=self.allocator.apply(observation,self.policy.select(observation))
                if state.cancel_requested and robot in self.goal_handles:
                    self.goal_handles.pop(robot).cancel_goal_async()
            for name,(target,token) in proposals.items():
                self.get_logger().info(f'Target for {name} in merge_map is {target}')
                self.send_goal(name,target,token)
            time.sleep(8)

    def send_goal(self,robot,target,token):
        if not self.robot_nav_clients[robot].wait_for_server(timeout_sec=2.):
            with self.lock:self.allocator.finish(robot,token,'server_unavailable')
            return
        with self.lock:
            state=self.allocator.robots[robot]
            if self.allocator.halted or state.cancel_requested or state.token!=token or state.state!='pending':
                return
            try:local,orientation=self.local_point(robot,target)
            except TransformException:
                self.allocator.finish(robot,token,'alignment_unavailable');return
            if not self.nav_goal_in_local_map(robot,local.x,local.y):
                self.allocator.finish(robot,token,'invalid_local_goal');return
            goal=NavigateToPose.Goal();goal.pose.header.frame_id='map';goal.pose.header.stamp=self.get_clock().now().to_msg()
            goal.pose.pose.position.x=local.x;goal.pose.pose.position.y=local.y;goal.pose.pose.orientation=orientation
            future=self.robot_nav_clients[robot].send_goal_async(goal,feedback_callback=lambda m:self.feedback_callback(robot,token,m))
            future.add_done_callback(lambda f:self.goal_response_callback(robot,token,f))

    def goal_response_callback(self,robot,token,future):
        handle=future.result()
        with self.lock:
            if not handle.accepted:self.allocator.finish(robot,token,'rejected');return
            uuid=bytes(handle.goal_id.uuid).hex()
            if not self.allocator.accepted(robot,token,uuid):
                handle.cancel_goal_async()
            else:
                self.goal_handles[robot]=handle
                self.get_logger().info(f'{robot} navigation goal accepted uuid={uuid}')
        handle.get_result_async().add_done_callback(lambda f:self.goal_result_callback(robot,token,f.result()))

    def feedback_callback(self,robot,token,message):
        with self.lock:
            state=self.allocator.robots[robot]
            if state.token==token:
                self.record(dict(kind='feedback',robot=robot,token=token,remaining=message.feedback.distance_remaining,sim=self.now()))

    def goal_result_callback(self,robot,token,result):
        with self.lock:
            self.allocator.tick(self.now())
            status={4:'succeeded',5:'canceled',6:'aborted'}.get(result.status,'unknown_terminal')
            if self.allocator.finish(robot,token,status):self.goal_handles.pop(robot,None)
            self.get_logger().info(f'{robot} navigation result status={result.status}')


def main(args=None):
    rclpy.init(args=args)
    parameters=Node('control_node');count=parameters.declare_parameter('robot_count',3).value
    control=HeadquartersControl(count)
    try:
        rclpy.spin(control)
        if control.worker_error:raise RuntimeError(control.worker_error)
    except ExternalShutdownException:
        if control.worker_error:raise RuntimeError(control.worker_error)
    except KeyboardInterrupt:control.get_logger().info('Shutting down exploration.')
    finally:
        with control.lock:
            control.allocator.tick(control.now());control.allocator.stop('controller_shutdown')
            control.record(dict(kind='evaluation_summary',sim=control.now(),metrics=control.evaluator.summary()))
            control.events.close()
        # Existing external supervisor cancels Nav2 and proves physical stopping.
        control.destroy_node();parameters.destroy_node()
        if rclpy.ok():rclpy.shutdown()


if __name__=='__main__':main()
