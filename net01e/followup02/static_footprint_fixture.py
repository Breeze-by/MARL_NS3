"""Bounded, no-motion installed Nav2 fixture; no Gazebo or NavigateToPose."""
import copy
import json
import math
from pathlib import Path
import signal
import subprocess
import time

import numpy as np
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from geometry_msgs.msg import TransformStamped, PolygonStamped
from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState
from nav2_msgs.action import ComputePathToPose
from nav2_msgs.msg import CostmapFilterInfo
from nav2_msgs.srv import GetCostmap
from nav_msgs.msg import OccupancyGrid
from tf2_ros import TransformBroadcaster
import yaml

ROOT=Path('/mnt')
OUT=Path('/tmp/fixture')
CASE=ROOT/'net01e/followup01/gz-runs/corr6201-v2-r03-b'
P0=(-.8554396247791896,4.361183122792712)
P1=(P0[0]+.75,P0[1])
GOAL=(3.700000000000002,2.6250000000000013)
BEGIN=time.monotonic()

def stop_signal(signum,frame):
    raise KeyboardInterrupt(f'signal {signum}')

def inside_polygon(x,y,points):
    inside=False
    for a,b in zip(points,points[1:]+points[:1]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside

class Fixture:
    def __init__(self,enabled,cells,origin,res):
        self.enabled=enabled;self.ns=f'/net01e_ghost_{str(enabled).lower()}'
        self.out=OUT/str(enabled).lower();self.out.mkdir(exist_ok=False)
        self.node=Node('fixture_'+str(enabled).lower(),namespace=self.ns)
        self.process=None;self.log=None;self.pose=P0;self.footprint=[]
        self.tf=TransformBroadcaster(self.node)
        self.timer=self.node.create_timer(.05,self.send_tf)
        qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.base_pub=self.node.create_publisher(OccupancyGrid,self.ns+'/base_map',qos)
        self.mask_pub=self.node.create_publisher(OccupancyGrid,self.ns+'/mask',qos)
        self.info_pub=self.node.create_publisher(CostmapFilterInfo,self.ns+'/info',qos)
        self.sub=self.node.create_subscription(PolygonStamped,self.ns+'/global_costmap/published_footprint',self.receive_footprint,10)
        self.cells=cells;self.origin=origin;self.res=res
        self.base=OccupancyGrid();self.base.header.frame_id='map'
        self.base.info.width=cells.shape[1];self.base.info.height=cells.shape[0];self.base.info.resolution=res
        self.base.info.origin.position.x,self.base.info.origin.position.y=origin
        self.base.info.origin.orientation.w=1.;self.base.data=cells.reshape(-1).tolist()
        yy,xx=np.indices(cells.shape);self.xx=origin[0]+(xx+.5)*res;self.yy=origin[1]+(yy+.5)*res
        self.sentinel=((self.xx-(P0[0]+1.5))**2+(self.yy-P0[1])**2<=.55**2)
        mask=copy.deepcopy(self.base);mask.data=np.where(self.sentinel,100,-1).astype(np.int8).reshape(-1).tolist()
        info=CostmapFilterInfo();info.type=0;info.base=0.;info.multiplier=1.;info.filter_mask_topic=self.ns+'/mask'
        self.publish_map();mask.header.stamp=self.node.get_clock().now().to_msg();self.mask_pub.publish(mask);self.info_pub.publish(info)
        source=yaml.safe_load((CASE/'peer_nav2_tb1.yaml').read_text())
        gc=copy.deepcopy(source['global_costmap']['global_costmap']['ros__parameters'])
        gc['use_sim_time']=False;gc['map_topic']=self.ns+'/base_map'
        gc['static_layer']['map_topic']=self.ns+'/base_map'
        gc['static_layer']['footprint_clearing_enabled']=enabled
        gc['obstacle_layer']['scan']['topic']=self.ns+'/empty_scan'
        gc['peer_keepout']['filter_info_topic']=self.ns+'/info'
        pc=copy.deepcopy(source['planner_server']['ros__parameters']);pc['use_sim_time']=False
        params={self.ns+'/planner_server':{'ros__parameters':pc},
                self.ns+'/global_costmap/global_costmap':{'ros__parameters':gc}}
        path=self.out/'params.yaml';path.write_text(yaml.safe_dump(params,sort_keys=False))
        self.argv=['/opt/ros/humble/lib/nav2_planner/planner_server','--ros-args','-r','__ns:='+self.ns,'--params-file',str(path)]
        (self.out/'argv.json').write_text(json.dumps(self.argv,indent=2)+'\n')
        self.log=(self.out/'planner.log').open('x')
        self.process=subprocess.Popen(self.argv,stdout=self.log,stderr=subprocess.STDOUT)
        self.lifecycle=self.node.create_client(ChangeState,self.ns+'/planner_server/change_state')
        self.costmap=self.node.create_client(GetCostmap,self.ns+'/global_costmap/get_costmap')
        self.action=ActionClient(self.node,ComputePathToPose,self.ns+'/compute_path_to_pose')

    def send_tf(self):
        t=TransformStamped();t.header.stamp=self.node.get_clock().now().to_msg();t.header.frame_id='map';t.child_frame_id='base_link'
        t.transform.translation.x,t.transform.translation.y=self.pose;t.transform.rotation.w=1.;self.tf.sendTransform(t)

    def receive_footprint(self,m):self.footprint=[[p.x,p.y] for p in m.polygon.points]

    def pump(self,seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if self.process.poll() is not None:raise RuntimeError('planner exited '+str(self.process.returncode))
            rclpy.spin_once(self.node,timeout_sec=min(.05,max(0,end-time.monotonic())))

    def future(self,f,timeout=5):
        rclpy.spin_until_future_complete(self.node,f,timeout_sec=timeout)
        if not f.done():raise TimeoutError('fixture future timeout')
        return f.result()

    def transition(self,transition):
        req=ChangeState.Request();req.transition.id=transition
        if not self.future(self.lifecycle.call_async(req)).success:raise RuntimeError('lifecycle transition failed '+str(transition))

    def ready(self):
        end=time.monotonic()+20
        while not self.lifecycle.service_is_ready() and time.monotonic()<end:self.pump(.05)
        if not self.lifecycle.service_is_ready():raise TimeoutError('planner lifecycle unavailable')
        self.transition(Transition.TRANSITION_CONFIGURE)
        self.transition(Transition.TRANSITION_ACTIVATE)
        if not self.costmap.wait_for_service(timeout_sec=2):raise TimeoutError('get_costmap unavailable')
        if not self.action.wait_for_server(timeout_sec=2):raise TimeoutError('ComputePath unavailable')
        self.pump(2.1)

    def publish_map(self):
        self.base.header.stamp=self.node.get_clock().now().to_msg();self.base_pub.publish(self.base)

    def snapshot(self,name):
        m=self.future(self.costmap.call_async(GetCostmap.Request())).map;meta=m.metadata
        grid=np.asarray(m.data,dtype=np.uint8).reshape(meta.size_y,meta.size_x)
        if grid.shape!=self.cells.shape:raise RuntimeError('costmap geometry differs from fixed raw map')
        if not self.footprint:raise RuntimeError('actual published footprint not received')
        polygon=self.footprint.copy()
        body=np.array([inside_polygon(float(x),float(y),polygon) for x,y in zip(self.xx.flat,self.yy.flat)]).reshape(grid.shape)
        oldbody=((self.xx-P0[0])**2+(self.yy-P0[1])**2<.27**2)
        outside_both=~(body|oldbody)
        occupied_outside=(self.cells==100)&outside_both
        unknown_outside=(self.cells==-1)&outside_both
        def at(xy):
            x=int((xy[0]-meta.origin.position.x)/meta.resolution);y=int((xy[1]-meta.origin.position.y)/meta.resolution)
            return dict(cell=[x,y],value=int(grid[y,x]))
        result=dict(name=name,wall_elapsed_s=time.monotonic()-BEGIN,pose=list(self.pose),
             frame=m.header.frame_id,origin=[meta.origin.position.x,meta.origin.position.y],resolution=meta.resolution,
             shape=list(grid.shape),actual_published_footprint=polygon,ghost_value=int(grid[194,106]),
             original_start=at(P0),current_start=at(self.pose),peer_sentinel_cells=int(self.sentinel.sum()),
             peer_sentinel_nonlethal=int(np.count_nonzero(grid[self.sentinel]!=254)),
             raw_occupied_outside_both_count=int(occupied_outside.sum()),
             raw_occupied_outside_both_not_lethal=int(np.count_nonzero(grid[occupied_outside]!=254)),
             raw_unknown_outside_both_new_free=int(np.count_nonzero(grid[unknown_outside]==0)))
        np.savez_compressed(self.out/(name+'.npz'),raw_uint8_grid=grid,current_polygon=np.asarray(polygon),current_body_mask=body)
        (self.out/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        if result['peer_sentinel_nonlethal'] or result['raw_occupied_outside_both_not_lethal'] or result['raw_unknown_outside_both_new_free']:
            raise RuntimeError('sentinel/body-external preservation check failed; see '+name+'.json')
        return result

    def plan(self):
        g=ComputePathToPose.Goal();g.planner_id='GridBased';g.use_start=True
        for msg,xy in ((g.start,P0),(g.goal,GOAL)):
            msg.header.frame_id='map';msg.header.stamp=self.node.get_clock().now().to_msg()
            msg.pose.position.x,msg.pose.position.y=xy;msg.pose.orientation.w=1.
        handle=self.future(self.action.send_goal_async(g))
        if not handle.accepted:raise RuntimeError('ComputePath goal rejected')
        response=self.future(handle.get_result_async());path=response.result.path
        result=dict(status=response.status,poses=len(path.poses),start=list(P0),goal=list(GOAL),
            endpoints=[[p.pose.position.x,p.pose.position.y] for p in (path.poses[:1]+path.poses[-1:])],
            length_m=sum(math.hypot(b.pose.position.x-a.pose.position.x,b.pose.position.y-a.pose.position.y) for a,b in zip(path.poses,path.poses[1:])))
        (self.out/'plan.json').write_text(json.dumps(result,indent=2)+'\n');return result

    def close(self):
        if self.process is None:return
        pid=self.process.pid
        self.process.send_signal(signal.SIGINT)
        try:self.process.wait(timeout=7)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=1)
        (self.out/'exit.json').write_text(json.dumps(dict(pid=pid,exit=self.process.returncode,reaped=True),indent=2)+'\n')
        self.log.close();self.action.destroy();self.node.destroy_node()

def main():
    signal.signal(signal.SIGTERM,stop_signal)
    with np.load(CASE/'controller/policy-trace/0009.npz',allow_pickle=False) as z:
        cells=z['tb1_local_cells'].copy();origin=z['tb1_local_origin'].tolist();res=float(z['tb1_local_resolution'])
    np.savez_compressed(OUT/'fixed-input.npz',cells=cells,origin=origin,resolution=res,start=P0,goal=GOAL)
    report=dict(status='RUNNING',no_Gazebo=True,no_NavigateToPose=True,no_velocity_commands=True,instances=[],
                input='B3 policy-trace/0009.npz tb1 raw own map; fixed recorded-TF composition; controlled empty scan and peer sentinel',
                limits=['No exact historical planner lock snapshot or layer/scan/peer consumption replay.','Static internal transformed footprint is not directly observable; published footprint is current Costmap2DROS output.'])
    rclpy.init()
    try:
        for enabled in (False,True):
            fixture=None
            try:
                fixture=Fixture(enabled,cells,origin,res);fixture.ready()
                first=fixture.snapshot('original-pose');plan=fixture.plan()
                if not enabled and (first['ghost_value']!=254 or plan['status']==4):raise RuntimeError('default mechanism did not reproduce')
                if enabled and (first['ghost_value']!=0 or plan['status']!=4):raise RuntimeError('true did not clear ghost and produce original-goal path')
                fixture.pose=P1;fixture.pump(2.1);moved=fixture.snapshot('moved-no-map')
                fixture.publish_map();fixture.pump(2.1);newmap=fixture.snapshot('moved-new-map')
                report['instances'].append(dict(enabled=enabled,first=first,plan=plan,moved_no_map=moved,moved_new_map=newmap))
            finally:
                if fixture:fixture.close()
        report['status']='COMPLETED_CONTROLLED_COMPARISON'
    except BaseException as e:
        report['status']='FAIL_STOP_NO_RETRY';report['error']=f'{type(e).__name__}: {e}'
        raise
    finally:
        report['wall_s']=time.monotonic()-BEGIN;(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');rclpy.shutdown()

if __name__=='__main__':main()
