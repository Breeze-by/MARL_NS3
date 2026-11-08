"""One native KeepoutFilter check: no Gazebo, planner, Action, or motion command."""
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from lifecycle_msgs.srv import ChangeState
from lifecycle_msgs.msg import Transition
from nav2_msgs.srv import GetCostmap
from nav2_msgs.msg import CostmapFilterInfo
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import TransformStamped
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster
from peer_keepout import peer_mask, RADIUS, SIZE, ORIGIN, RESOLUTION
import yaml

OUT=Path('/mnt/evidence/native-compact-peer-check-01')


def main():
    OUT.mkdir(exist_ok=False)
    params={'use_sim_time':False,'global_frame':'odom','robot_base_frame':'base_link',
        'rolling_window':True,'width':8,'height':8,'origin_x':-4.,'origin_y':-4.,'resolution':.05,
        'robot_radius':.25,'update_frequency':5.,'publish_frequency':2.,'track_unknown_space':True,
        'plugins':['static_layer'],'static_layer':{'plugin':'nav2_costmap_2d::StaticLayer',
            'map_topic':'/native_peer_test/base_map','map_subscribe_transient_local':True},
        'filters':['peer_keepout'],'always_send_full_costmap':True,
        'peer_keepout':{'plugin':'nav2_costmap_2d::KeepoutFilter','enabled':True,
                        'filter_info_topic':'/native_peer_test/info','transform_tolerance':.2}}
    path=OUT/'params.yaml';path.write_text(yaml.safe_dump({'/**':{'ros__parameters':params}}))
    rclpy.init();node=Node('peer_native_fixture')
    qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
    info_pub=node.create_publisher(CostmapFilterInfo,'/native_peer_test/info',qos)
    mask_pub=node.create_publisher(OccupancyGrid,'/native_peer_test/mask',qos)
    base_pub=node.create_publisher(OccupancyGrid,'/native_peer_test/base_map',qos)
    tf=StaticTransformBroadcaster(node)
    transforms=[]
    for parent,child,x,y in [('merge_map','odom',2.,-1.),('odom','base_link',0.,0.)]:
        t=TransformStamped();t.header.stamp=node.get_clock().now().to_msg();t.header.frame_id=parent;t.child_frame_id=child
        t.transform.translation.x=x;t.transform.translation.y=y;t.transform.rotation.w=1.;transforms.append(t)
    tf.sendTransform(transforms)
    info=CostmapFilterInfo();info.type=0;info.base=0.;info.multiplier=1.;info.filter_mask_topic='/native_peer_test/mask';info_pub.publish(info)
    base=OccupancyGrid();base.header.frame_id='odom';base.header.stamp=node.get_clock().now().to_msg()
    base.info.width=base.info.height=160;base.info.resolution=.05
    base.info.origin.position.x=base.info.origin.position.y=-4.;base.info.origin.orientation.w=1.
    yy,xx=np.indices((160,160));xx=-4+(xx+.5)*.05;yy=-4+(yy+.5)*.05
    primary=np.zeros((160,160),dtype=np.int8)
    for px,py,value in [(2.,.4,-1),(0.,3.,-1),(0.,-3.,100)]:primary[(abs(xx-px)<.1)&(abs(yy-py)<.1)]=value
    base.data=primary.reshape(-1).tolist();base_pub.publish(base)
    def publish(center):
        m=OccupancyGrid();m.header.frame_id='merge_map';m.header.stamp=node.get_clock().now().to_msg()
        m.info.width=m.info.height=SIZE;m.info.resolution=RESOLUTION
        m.info.origin.position.x,m.info.origin.position.y=ORIGIN;m.info.origin.orientation.w=1.
        m.data=peer_mask('tb1',{'tb1':(2.,-1.),'tb2':center},ORIGIN).reshape(-1).tolist();mask_pub.publish(m)
    publish((4.,-1.))
    log=(OUT/'costmap-native.log').open('x')
    process=subprocess.Popen(['ros2','run','nav2_costmap_2d','nav2_costmap_2d','--ros-args',
        '-r','__ns:=/native_peer_test','--params-file',str(path)],stdout=log,stderr=subprocess.STDOUT)
    def services(suffix,type_):
        end=time.monotonic()+25
        while time.monotonic()<end:
            names=[n for n,types in node.get_service_names_and_types() if n.startswith('/costmap/') and n.endswith(suffix)]
            if len(names)==1:
                client=node.create_client(type_,names[0])
                if client.wait_for_service(timeout_sec=.1):return client,names[0]
            rclpy.spin_once(node,timeout_sec=.05)
        raise RuntimeError('Native costmap service unavailable: '+suffix)
    def call(client,request):
        f=client.call_async(request);rclpy.spin_until_future_complete(node,f,timeout_sec=10)
        if not f.done():raise RuntimeError('Native costmap service timeout')
        return f.result()
    try:
        lifecycle,life_name=services('/change_state',ChangeState)
        for transition in (Transition.TRANSITION_CONFIGURE,Transition.TRANSITION_ACTIVATE):
            request=ChangeState.Request();request.transition.id=transition
            assert call(lifecycle,request).success
        client,cost_name=services('/get_costmap',GetCostmap)
        def sample(expected):
            end=time.monotonic()+10
            last=None
            while time.monotonic()<end:
                m=call(client,GetCostmap.Request()).map;meta=m.metadata
                values=[]
                for x,y in [(2.,0.),(2.,.4),(-2.,0.),(0.,3.),(0.,-3.),(0.,0.)]:
                    col=int((x-meta.origin.position.x)/meta.resolution);row=int((y-meta.origin.position.y)/meta.resolution)
                    values.append(int(m.data[row*meta.size_x+col]))
                last=values
                if values==expected:return values
                rclpy.spin_once(node,timeout_sec=.1)
            raise AssertionError((expected,last))
        first=sample([254,254,0,255,254,0]);publish((0.,-1.));moved=sample([0,255,254,255,254,0])
        result={'pass':True,'native_filter':'nav2_costmap_2d::KeepoutFilter','first':first,'moved':moved,
            'query_points_odom':[[2,0],[2,.4],[-2,0],[0,3],[0,-3],[0,0]],'mask_frame':'merge_map','costmap_frame':'odom',
            'merge_map_from_odom_translation':[2,-1],'old_region_cleared':moved[0]==0,
            'unknown_preserved':moved[1]==moved[3]==255,'occupied_preserved':moved[4]==254,
            'own_center_unblocked':moved[5]==0,'background_mask':-1,'rolling_window':True,'production_radius_m':RADIUS,
            'lifecycle_service':life_name,'get_costmap_service':cost_name,'Gazebo':0,'Nav2_goal_requests':0}
        (OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close();node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
