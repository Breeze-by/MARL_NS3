"""Central goal contract. ROS-free; policies have no actuator or truth access."""
from dataclasses import dataclass
from types import MappingProxyType
from numbers import Integral
import math
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from . import frontier

KEEP, WAIT = -1, -2
CONTRACT = 'base02-v1'
LOCAL_CONTRACT = 'rl03-local-reachable-v1'
APPROACH_CONTRACT = 'rl04-shared-frontier-approach-v1'
APPROACH_V2_CONTRACT = 'rl04-shared-frontier-approach-v2'


def frozen(value):
    if isinstance(value, dict): return MappingProxyType({k:frozen(v) for k,v in value.items()})
    if isinstance(value, (list,tuple)): return tuple(frozen(v) for v in value)
    return value


@dataclass(frozen=True)
class JointAction:
    decision_id: int
    map_version: int
    choices: tuple

    def __post_init__(self):
        object.__setattr__(self,'choices',tuple(int(v) if isinstance(v,Integral) and not isinstance(v,bool) else v for v in self.choices))


@dataclass
class Robot:
    name: str
    pose: tuple = None
    stamp: float = None
    velocity: tuple = (0., 0., 0.)
    state: str = 'idle'
    target: tuple = None
    token: int = 0
    uuid: str = None
    started: float = None
    last_status: str = 'none'
    last_success: tuple = None
    wait_count: int = 0
    condition: str = 'awaiting_observation'
    cancel_requested: bool = False


def distances(matrix, start, resolution, return_predecessors=False):
    """Shortest known-free 8-connected grid distance, no corner cutting (m)."""
    h, w = matrix.shape
    free = matrix == 0
    indices = np.arange(h*w).reshape(h,w)
    sources, targets, weights = [], [], []
    # The caller has already made the current cell free. Four undirected
    # neighbour pairs produce the identical eight directed moves as before.
    for dr, dc in ((0,1),(1,0),(1,1),(1,-1)):
        rows=slice(0,h-dr); columns=slice(max(0,-dc),min(w,w-dc))
        next_rows=slice(dr,h); next_columns=slice(max(0,-dc)+dc,min(w,w-dc)+dc)
        legal=free[rows,columns] & free[next_rows,next_columns]
        if dr and dc:
            legal &= free[rows,next_columns] & free[next_rows,columns]
        a=indices[rows,columns][legal];b=indices[next_rows,next_columns][legal]
        sources.extend((a,b));targets.extend((b,a))
        weights.append(np.full(2*len(a),math.hypot(dr,dc)*resolution))
    graph=csr_matrix((np.concatenate(weights),(np.concatenate(sources),np.concatenate(targets))),shape=(h*w,h*w))
    result=dijkstra(graph,directed=True,indices=start[0]*w+start[1],return_predecessors=return_predecessors)
    costs,predecessors=result if return_predecessors else (result,None)
    reachable={(int(i//w),int(i%w)):float(costs[i]) for i in np.flatnonzero(np.isfinite(costs))}
    return (reachable,predecessors) if return_predecessors else reachable


def route_prefix(path, length):
    """Fixed initial route arc length; not a time-synchronised Nav2 trajectory."""
    result=[path[0]]
    for a,b in zip(path,path[1:]):
        distance=math.dist(a,b)
        if distance>length:
            result.append(tuple(a[i]+(b[i]-a[i])*length/distance for i in (0,1)))
            break
        result.append(b);length-=distance
    return tuple(result)


def route_separation(left, right):
    def point_segment(p,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1];square=dx*dx+dy*dy
        t=0. if square==0 else max(0.,min(1.,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/square))
        return math.dist(p,(a[0]+t*dx,a[1]+t*dy))
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def segment_distance(a,b,c,d):
        if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:return 0.
        return min(point_segment(a,c,d),point_segment(b,c,d),point_segment(c,a,b),point_segment(d,a,b))
    aa=list(zip(left,left[1:])) or [(left[0],left[0])]
    bb=list(zip(right,right[1:])) or [(right[0],right[0])]
    return min(segment_distance(a,b,c,d) for a,b in aa for c,d in bb)


def observed_approach(path, local_inflated, position, admissible, pose, goal_tolerance):
    """Last admissible local prefix before an unknown edge, never a known wall.

    Diagonal support cells are part of the edge. Positive inflated occupancy
    rejects even if another support cell is unknown. No unknown edge => no bridge.
    """
    prefix=[path[0]]
    for previous,cell in zip(path,path[1:]):
        required=[cell]
        if previous[0]!=cell[0] and previous[1]!=cell[1]:
            required += [(previous[0],cell[1]),(cell[0],previous[1])]
        if any(local_inflated[p]>0 for p in required):return None
        unknown=[p for p in required if local_inflated[p]<0]
        if unknown:
            for target in reversed(prefix):
                if math.dist(position(target),pose[:2])>goal_tolerance and admissible(target):
                    return target,tuple(unknown)
            return None
        prefix.append(cell)
    return None


class TraditionalPolicy:
    """Exact BASE-01 ordering/ranking and post-selection last-target veto."""
    def select(self, observation):
        choices = []
        for i, robot in enumerate(observation['robots']):
            if robot['state'] != 'idle':
                choices.append(KEEP)
                continue
            if observation['trigger'] is not None and observation['trigger'] != robot['id']:
                choices.append(WAIT)
                continue
            eligible = [j for j, candidate in enumerate(observation['candidates'])
                        if candidate['robot'] == robot['id'] and candidate['traditional_eligible']]
            if not eligible:
                choices.append(WAIT)
                continue
            best = max(eligible,key=lambda j:observation['candidates'][j]['traditional_score'])
            target = observation['candidates'][best]['position']
            if robot['last_success'] and math.dist(target,robot['last_success']) < .5:
                choices.append(WAIT)
            else:
                choices.append(best)
        return JointAction(observation['decision_id'],observation['map_version'],tuple(choices))


class TestPolicy:
    """Deterministic fixture policy, never a learned algorithm or ROS autonomy."""
    def select(self, observation):
        choices = []
        for i, robot in enumerate(observation['robots']):
            legal = [j for j,v in enumerate(observation['action_mask'][i]) if v]
            choices.append(KEEP if robot['state'] != 'idle' else legal[0] if legal else WAIT)
        return JointAction(observation['decision_id'],observation['map_version'],tuple(choices))


class RLPolicy:
    def __init__(self, predict=None):
        self.predict = predict

    def select(self, observation):
        if self.predict is None:
            raise RuntimeError('RL policy is not attached; no fallback or training is performed')
        return JointAction(observation['decision_id'],observation['map_version'],tuple(self.predict(observation)))


def policy_for(mode, predict=None):
    return {'traditional':TraditionalPolicy, 'test':TestPolicy, 'rl':lambda:RLPolicy(predict)}[mode]()


def idle_body_goal_valid(observation, owner, target):
    """Goal-endpoint guard against peers idle in this immutable joint snapshot."""
    clearance=observation.get('idle_body_goal_clearance_m')
    return clearance is None or all(name==owner or math.dist(target,pose[:2])>=clearance
        for name,pose in observation['idle_body_positions'].items())


class Allocator:
    def __init__(self, robot_ids=('tb1','tb2','tb3'), local_goal_valid=lambda *args: True,
                 emit=lambda event: None, task_timeout_s=None, task_roi=None,
                 candidate_mode='legacy', local_navigation_grid=None, navigation_path_budget_m=None,
                 navigation_goal_tolerance_m=.25,seed_connection=None):
        if candidate_mode not in ('legacy', 'rl03_local_v1','rl04_approach_v1','rl04_approach_v2'):
            raise ValueError('Unknown candidate mode')
        if candidate_mode != 'legacy' and (local_navigation_grid is None or
                navigation_path_budget_m is None or navigation_path_budget_m <= 0):
            raise ValueError('Local candidate mode needs received grids and a positive path budget')
        self.robots = {r:Robot(r) for r in robot_ids}
        self.candidate_mode = candidate_mode
        self.local_navigation_grid = local_navigation_grid
        self.navigation_path_budget_m = navigation_path_budget_m
        self.navigation_goal_tolerance_m = navigation_goal_tolerance_m
        self.goal_separation_m=.7 if candidate_mode=='rl04_approach_v2' else .2
        self.local_goal_valid = local_goal_valid
        self.peer_goal_valid = None
        self.planner_goal_admissibility = False
        self.peer_routing_mask = None
        self.initial_route_conflicts = None
        self.seed_connection = seed_connection
        self.self_body_route_exclusion = False
        self.idle_body_goal_clearance_m = None
        self.emit = emit
        self.task_timeout_s = task_timeout_s
        self.task_roi = task_roi
        self.map = None
        self.map_version = 0
        self.decision_id = 0
        self.visited, self.failed = [], {r:[] for r in robot_ids}
        self.history = []
        self.halted = None
        self.now = 0.

    def event(self, kind, **values):
        self.emit(dict(kind=kind,sim=self.now,**values))

    def update_map(self, cells, resolution, origin, stamp, source='/merge_map'):
        if self.task_roi is not None:
            from .observations import project_observed
            cells=project_observed(cells,resolution,origin,self.task_roi)
            resolution,origin=.05,tuple(self.task_roi[:2])
        cells = np.array(cells,dtype=np.int16,copy=True)
        if self.map is None or resolution != self.map['resolution'] or tuple(origin) != self.map['origin'] or not np.array_equal(cells,self.map['cells']):
            self.map_version += 1
            self.event('map_changed',map_version=self.map_version,known_area_m2=float(np.count_nonzero(cells >= 0)*resolution**2))
        cells = np.frombuffer(cells.tobytes(),dtype=cells.dtype).reshape(cells.shape)
        self.map = dict(cells=cells,resolution=resolution,origin=tuple(origin),stamp=stamp,
                        source=source,frame='merge_map',version=self.map_version)

    def update_robot(self, robot, pose, stamp, velocity):
        state = self.robots[robot]
        state.pose, state.stamp, state.velocity = pose, stamp, velocity

    def tick(self, now):
        self.now = now
        for r in self.robots.values():
            if r.state != 'idle' and self.task_timeout_s is not None and now-r.started > self.task_timeout_s and not r.cancel_requested:
                r.cancel_requested = True
                r.condition = 'task_timeout_cancel_required'
                self.event('cancel_required',robot=r.name,token=r.token,uuid=r.uuid,reason='task_timeout')

    def get_observation(self, trigger=None):
        self.decision_id += 1
        candidates, robot_rows, masks = [], [], []
        initial_routes=(self.initial_route_conflicts is not None and not self.history and
            all(r.state=='idle' for r in self.robots.values()))
        idle_guard=({} if self.idle_body_goal_clearance_m is None else dict(
            idle_body_goal_clearance_m=self.idle_body_goal_clearance_m,
            idle_body_positions={r.name:r.pose for r in self.robots.values()
                                 if r.state=='idle' and r.pose is not None}))
        for robot in self.robots.values():
            row = dict(id=robot.name,pose=robot.pose,pose_stamp=robot.stamp,
                pose_source=f'/{robot.name}/odom + namespaced TF',velocity=robot.velocity,
                state=robot.state,target=robot.target,task_token=robot.token,action_uuid=robot.uuid,
                last_status=robot.last_status,last_success=robot.last_success,
                goal_duration_s=None if robot.started is None else self.now-robot.started,
                condition=robot.condition,cancel_requested=robot.cancel_requested)
            robot_rows.append(row)
            if self.map is None or robot.pose is None:
                continue
            m=self.map; h,w=m['cells'].shape; res=m['resolution']; ox,oy=m['origin']
            column=math.floor((robot.pose[0]-ox)/res); r=math.floor((robot.pose[1]-oy)/res)
            if not (0 <= r < h and 0 <= column < w):
                continue
            data=frontier.costmap(m['cells'],w,h,res)
            shared_inflated=data.copy()
            data[r,column]=0; data[data>5]=1
            data,groups=frontier.assign_groups(frontier.frontierB(data))
            approach_mode=self.candidate_mode in ('rl04_approach_v1','rl04_approach_v2')
            groups=([g for g in sorted(groups.items(),key=lambda x:len(x[1]),reverse=True) if len(g[1])>2]
                if approach_mode else frontier.fGroups(groups))
            data[data<0]=1
            local_paths = None
            connection=()
            routing_data=data
            peer_blocked=(None if self.peer_routing_mask is None else self.peer_routing_mask(robot.name,m))
            local_data=None
            if self.candidate_mode != 'legacy':
                local = self.local_navigation_grid(robot.name, m)
                if local is None:
                    continue
                if local.shape != m['cells'].shape:
                    raise ValueError('Local navigation grid must use the shared grid coordinates')
                local_inflated=frontier.costmap(local,w,h,res)
                routing_shared_cells=m['cells'].copy() if self.self_body_route_exclusion else None
                if self.seed_connection is not None:
                    if routing_shared_cells is None:
                        connection=self.seed_connection(robot.name,m,local,shared_inflated,local_inflated,(r,column)) or ()
                    else:
                        connection=self.seed_connection(robot.name,m,local,shared_inflated,local_inflated,(r,column),
                            routing_shared_cells=routing_shared_cells) or ()
                if routing_shared_cells is not None:
                    routing_data=frontier.costmap(routing_shared_cells,w,h,res)
                    routing_data[r,column]=0; routing_data[routing_data<0]=1
                    routing_data[routing_data>5]=1
                local_routing_inflated=local_inflated.copy()
                if connection:
                    routing_data=routing_data.copy()
                    for cell in connection:
                        routing_data[cell]=0
                        local_routing_inflated[cell]=0
                local_data=local_routing_inflated.copy()
                local_data[local_data!=0]=1; local_data[r,column]=0
            if peer_blocked is not None:
                routing_data=routing_data.copy();routing_data[peer_blocked]=1
                if local_data is not None:local_data[peer_blocked]=1
                if peer_blocked[r,column]:continue
            if local_data is not None:
                if initial_routes:local_paths,local_predecessors=distances(local_data,(r,column),res,return_predecessors=True)
                else:local_paths=distances(local_data,(r,column),res)
            if approach_mode:path_costs,predecessors=distances(routing_data,(r,column),res,return_predecessors=True)
            else:path_costs=distances(routing_data,(r,column),res)
            reachable=path_costs
            blocked=[*self.visited,*self.failed[robot.name]]
            assigned=[q.target for q in self.robots.values() if q.target is not None]
            robot_begin=len(candidates)
            for group_id,cells in groups:
                center=frontier.calculate_centroid([p[0] for p in cells],[p[1] for p in cells])
                shared_free=[p for p in cells if p in reachable]
                free=shared_free
                metadata={}
                if local_paths is not None:
                    def position(p):return ((p[1]+.5)*res+ox,(p[0]+.5)*res+oy)
                    def admissible(p):
                        target=position(p)
                        return ((not self.planner_goal_admissibility or self.local_goal_valid(robot.name,*target)) and
                            idle_body_goal_valid(idle_guard,robot.name,target) and
                            (self.peer_goal_valid is None or self.peer_goal_valid(robot.name,target)) and
                            local[p]==0 and p in local_paths and
                            (not (connection or self.self_body_route_exclusion) or (shared_inflated[p]==0 and local_inflated[p]==0)) and
                            local_paths[p] <= self.navigation_path_budget_m and
                            not any(math.dist(target,q)<.2 for q in blocked) and
                            not any(math.dist(target,q)<self.goal_separation_m for q in assigned) and
                            (robot.last_success is None or math.dist(target,robot.last_success)>=.5))
                    free=[p for p in free if admissible(p)]
                    if approach_mode and not free and shared_free and not any(local[p]==0 and p in local_paths for p in shared_free):
                        endpoint=min(shared_free,key=lambda p:((p[0]-center[0])**2+(p[1]-center[1])**2,p))
                        path=[endpoint]
                        while path[-1]!=(r,column):
                            previous=int(predecessors[path[-1][0]*w+path[-1][1]])
                            path.append(divmod(previous,w))
                        path.reverse()
                        bridge=observed_approach(path,local_routing_inflated,position,admissible,
                            robot.pose,self.navigation_goal_tolerance_m)
                        if bridge is not None:
                            target_cell,unknown=bridge;free=[target_cell]
                            metadata=dict(kind='approach',shared_frontier_position=position(endpoint),
                                remaining_shared_path_m=path_costs[endpoint]-path_costs[target_cell],
                                unknown_boundary_cells=unknown)
                if not free:
                    continue
                rr,cc=min(free,key=lambda p:((p[0]-center[0])**2+(p[1]-center[1])**2,p))
                target=((cc+.5)*res+ox,(rr+.5)*res+oy)
                distance=math.sqrt((r-center[0])**2+(column-center[1])**2)
                eligible=((local_paths is not None or distance <= frontier.max_distance) and
                    not any(math.dist(target,p)<.2 for p in blocked) and
                    not any(math.dist(target,p)<self.goal_separation_m for p in assigned) and
                    idle_body_goal_valid(idle_guard,robot.name,target) and
                    (self.peer_goal_valid is None or self.peer_goal_valid(robot.name,target)))
                local_valid=self.local_goal_valid(robot.name,*target)
                last_valid=robot.last_success is None or math.dist(target,robot.last_success)>=.5
                candidate=dict(index=len(candidates),robot=robot.name,group_id=group_id,
                    position=target,frame='merge_map',reachable=True,path_cost_estimate_m=(path_costs if local_paths is None else local_paths)[(rr,cc)],
                    information_gain_proxy_m2=len(cells)*res**2,proxy='frontier cell area; not unseen truth',
                    traditional_score=len(cells)/(distance+1e-6),traditional_eligible=eligible,
                    valid=bool(eligible and local_valid and last_valid),local_map_valid=local_valid)
                if approach_mode:
                    candidate.update(metadata or dict(kind='frontier',shared_frontier_position=target,remaining_shared_path_m=0.,unknown_boundary_cells=()))
                    candidate['proxy']='associated shared-frontier cell area; approach gain may be delayed'
                if initial_routes:
                    path=[(rr,cc)]
                    while path[-1]!=(r,column):
                        path.append(divmod(int(local_predecessors[path[-1][0]*w+path[-1][1]]),w))
                    path.reverse()
                    route=[robot.pose[:2]]+[((cc+.5)*res+ox,(rr+.5)*res+oy) for rr,cc in path]
                    candidate['initial_route_prefix']=route_prefix(route,self.initial_route_conflicts[0])
                candidates.append(candidate)
            if approach_mode:
                raw=candidates[robot_begin:];unique=[]
                for candidate in sorted(raw,key=lambda c:c['traditional_score'],reverse=True):
                    if candidate['valid'] and not any(math.dist(candidate['position'],c['position'])<.2 for c in unique):
                        unique.append(candidate)
                selected={c['index'] for c in unique}
                candidates[robot_begin:]=[c for c in raw if c['index'] in selected][:5]
        if self.candidate_mode in ('rl04_approach_v1','rl04_approach_v2'):
            for index,candidate in enumerate(candidates):candidate['index']=index
        for robot in robot_rows:
            masks.append(tuple(c['robot']==robot['id'] and c['valid'] and robot['state']=='idle' and not self.halted for c in candidates))
        endpoint_conflicts=tuple((i,j) for i,c in enumerate(candidates) for j,d in enumerate(candidates)
            if i<j and math.dist(c['position'],d['position'])<self.goal_separation_m)
        route_conflicts=(tuple((i,j) for i,c in enumerate(candidates) for j,d in enumerate(candidates)
            if i<j and c['robot']!=d['robot'] and route_separation(
                c['initial_route_prefix'],d['initial_route_prefix'])<self.initial_route_conflicts[1])
            if initial_routes else ())
        contract={'legacy':CONTRACT,'rl03_local_v1':LOCAL_CONTRACT,'rl04_approach_v1':APPROACH_CONTRACT,
            'rl04_approach_v2':APPROACH_V2_CONTRACT}[self.candidate_mode]
        return frozen(dict(contract=contract,decision_id=self.decision_id,map_version=self.map_version,
            sim_stamp=self.now,trigger=trigger,map=None if self.map is None else dict(self.map),
            robots=tuple(robot_rows),candidates=tuple(candidates),action_mask=tuple(masks),
            keep_mask=tuple(r['state']!='idle' and not self.halted for r in robot_rows),
            wait_mask=tuple(r['state']=='idle' and not self.halted and not any(mask) for r,mask in zip(robot_rows,masks)),
            valid_counts=tuple(sum(mask) for mask in masks),assigned={r.name:r.target for r in self.robots.values()},
            candidate_conflicts=tuple(sorted(set(endpoint_conflicts)|set(route_conflicts))),
            **(dict(initial_route_rule='first-idle-prefix-v1',initial_route_length_m=self.initial_route_conflicts[0],
                initial_route_separation_m=self.initial_route_conflicts[1],
                endpoint_candidate_conflicts=endpoint_conflicts,initial_route_candidate_conflicts=route_conflicts) if initial_routes else {}),
            history=tuple(dict(e) for e in self.history),halted=self.halted,**idle_guard,
            **({'goal_separation_m':self.goal_separation_m} if self.candidate_mode=='rl04_approach_v2' else {})))

    def apply(self, observation, action):
        """Validate a joint snapshot; reserve all accepted targets before dispatch."""
        if self.halted:
            raise RuntimeError('Allocator halted: '+self.halted)
        if action.decision_id != observation['decision_id'] or action.decision_id != self.decision_id or action.map_version != self.map_version or observation['map_version'] != self.map_version:
            raise ValueError('Stale candidate snapshot')
        if any(r.token!=row['task_token'] or r.state!=row['state'] for r,row in zip(self.robots.values(),observation['robots'])):
            raise ValueError('Task ownership changed after snapshot')
        if len(action.choices) != len(self.robots):
            raise ValueError('Expected one action per robot')
        if any(type(v) is not int for v in action.choices):
            raise ValueError('Actions must be integer indices or KEEP/WAIT; bool/float are invalid')
        if observation.get('joint_assignment_rule')=='maximum-participation-v1':
            from .joint import slot_mask,choice_to_slot
            for row,choice in enumerate(action.choices):
                slot=choice_to_slot(choice)
                if not 0<=slot<17 or not slot_mask(observation,row,action.choices[:row])[slot]:
                    raise ValueError('Joint action violates maximum-participation conditional mask')
        proposals, rejected = {}, {}
        for i,(name,robot) in enumerate(self.robots.items()):
            choice=action.choices[i]
            # A traditional single-robot tick has no rights over other idle robots.
            if observation['trigger'] is not None and name != observation['trigger']:
                continue
            reason=None
            if robot.state != 'idle':
                if choice != KEEP: reason='active_task_protected'
            elif choice == WAIT:
                from .joint import candidate_mask
                prefix=tuple(action.choices[j] if n in proposals else WAIT
                             for j,n in enumerate(self.robots) if j<i)
                available=candidate_mask(observation,i,prefix)
                if any(available): reason='wait_with_available_work'
                robot.wait_count+=1
                robot.condition='stalled_wait' if robot.wait_count>=5 else 'no_candidate_wait'
                self.event('wait',robot=name,condition=robot.condition,valid_count=sum(available))
            elif type(choice) is not int or choice < 0 or choice >= len(observation['candidates']):
                reason='invalid_candidate_index'
            else:
                c=observation['candidates'][choice]; target=c['position']
                if not observation['action_mask'][i][choice] or not self.local_goal_valid(name,*target):
                    reason='candidate_masked_or_invalid'
                    # Preserve BASE-01's failed local-goal exclusion after selection.
                    if c['robot']==name and c['traditional_eligible'] and c['local_map_valid'] is False:
                        self.failed[name].append(target)
                elif not idle_body_goal_valid(observation,name,target):
                    reason='idle_body_goal_conflict'
                elif any(q.target is not None and math.dist(target,q.target)<self.goal_separation_m for q in self.robots.values()):
                    reason='target_conflict'
                if reason is None:
                    robot.token+=1; robot.target=target; robot.uuid=None; robot.started=self.now
                    robot.state='pending'; robot.wait_count=0; robot.condition='assigned'; robot.cancel_requested=False
                    proposals[name]=(target,robot.token)
                    self.event('goal_reserved',robot=name,target=target,token=robot.token,decision_id=self.decision_id)
            if reason:
                rejected[name]=reason
                self.event('action_rejected',robot=name,reason=reason,choice=choice)
        return proposals,rejected

    def accepted(self, robot, token, uuid):
        r=self.robots[robot]
        if self.halted or r.cancel_requested or r.token!=token or r.state!='pending': return False
        r.uuid=uuid; r.state='active'
        self.event('goal_accepted',robot=robot,token=token,uuid=uuid)
        return True

    def finish(self, robot, token, status):
        r=self.robots[robot]
        if r.token!=token or r.state=='idle': return False
        if status=='succeeded': self.visited.append(r.target); r.last_success=r.target
        if status in ('aborted','rejected','invalid_local_goal'): self.failed[robot].append(r.target)
        event=dict(robot=robot,token=token,uuid=r.uuid,target=r.target,status=status,sim=self.now)
        self.history.append(event); self.event('goal_terminal',**{k:v for k,v in event.items() if k!='sim'})
        r.last_status=status; r.state='idle'; r.target=None; r.uuid=None; r.started=None
        r.condition='ready_after_'+status; r.cancel_requested=False
        return True

    def stop(self, reason):
        self.halted=reason
        self.event('allocator_halted',reason=reason)
        # Transport must cancel these and prove physical stop. This never asserts it.
        return {r.name:r.uuid for r in self.robots.values() if r.state!='idle'}
