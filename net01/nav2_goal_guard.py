"""Explicit NavFn-cell validity and active original-goal cancellation adapter.

No target replacement, extra subscriber, timeout or synthetic Action terminal.
"""
import json
import math
from pathlib import Path
import time

VERSION='navfn-round-active-goal-v1'


def occupied_navfn_cell(grid,x,y):
    """Same nonnegative std::round lattice as NavFn, not Python ties-to-even."""
    dx=x-grid.info.origin.position.x;dy=y-grid.info.origin.position.y
    if dx<0 or dy<0:return False
    col=math.floor(dx/grid.info.resolution+.5);row=math.floor(dy/grid.info.resolution+.5)
    return (0<=col<grid.info.width and 0<=row<grid.info.height
        and grid.data[row*grid.info.width+col]==100)


class Nav2GoalGuard:
    def __init__(self,node,contract):
        self.node=node;self.contract=contract;self.requests={};self.cancellations=[]
        self.assignment_rejections=0;self.finished=False
        self.directory=Path(node.events.name).parent

    def observe_request(self,event):
        # Only primitives observed at the actual original send_goal_async gate.
        # Missing evidence cannot be replaced with a later state.target/TF.
        if (not event.get('actual_goal_frame') or not event.get('request_uuid')
            or event.get('token') is None or len(event.get('actual_goal_position',()))<2):return
        self.requests[event['robot']]=dict(token=event['token'],uuid=event['request_uuid'],
            frame=event['actual_goal_frame'],xy=list(event['actual_goal_position'][:2]),
            request_sim=event['sim'],actual_goal_stamp=event.get('actual_goal_stamp'))

    def map_received(self,message,robot):
        node=self.node
        if node.local_maps.get(robot) is not message:return
        request=self.requests.get(robot)
        if request is None or node.allocator.halted:return
        state=node.allocator.robots[robot]
        if (state.state!='active' or state.token!=request['token'] or state.uuid!=request['uuid']
            or state.cancel_requested or request['frame']!=message.header.frame_id):return
        now=node.now();stamp=message.header.stamp.sec+message.header.stamp.nanosec/1e9
        age=now-stamp
        if not 0<=age<=self.contract['fresh_map_max_age_sim_s']:return
        if not occupied_navfn_cell(message,*request['xy']):return
        state.cancel_requested=True
        state.condition='goal_occupied_cancel_required'
        self.cancellations.append(dict(robot=robot,token=state.token,uuid=state.uuid,
            original_goal_frame=request['frame'],original_goal_xy=request['xy'],
            original_goal_stamp=request['actual_goal_stamp'],map_stamp=stamp,map_source_age_sim_s=age,
            sim=now,monotonic_ns=time.monotonic_ns(),realtime_ns=time.time_ns(),
            cause='fresh_received_own_map_NavFn_round_cell_100',
            cache_is_original_callback_object=True,terminal_synthesized=False))
        node.dispatch_requested_cancels()

    def finish(self):
        if self.finished:return
        self.finished=True
        (self.directory/'nav2-goal-guard.json').write_text(json.dumps(dict(contract=self.contract,
            assignment_rejections=self.assignment_rejections,observed_actual_requests=self.requests,
            cancellation_requests=self.cancellations,
            scope='Original actual map-frame Goal primitive; cancellation admission only. State stays active until original real terminal callback; no extra business event.'),indent=2)+'\n')


def install_goal_guard(node,profile):
    contract=profile['nav2_goal_guard']
    if (contract['id']!=VERSION or contract['occupied_value']!=100
        or contract['fresh_map_max_age_sim_s']!=2.0):
        raise ValueError('Unknown explicit NavFn goal guard contract')
    guard=Nav2GoalGuard(node,contract)
    original_valid=node.nav_goal_in_local_map
    original_map=node.local_map_callback
    def valid(robot,x,y,*args,**kwargs):
        if not original_valid(robot,x,y,*args,**kwargs):return False
        grid=node.local_maps.get(robot)
        if grid is not None and occupied_navfn_cell(grid,x,y):
            guard.assignment_rejections+=1
            return False
        return True
    def received(message,robot):
        with node.lock:
            result=original_map(message,robot)
            guard.map_received(message,robot)
            return result
    node.nav_goal_in_local_map=valid
    node.local_map_callback=received
    node._nav2_goal_guard=guard
    return guard
