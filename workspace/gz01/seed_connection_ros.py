"""ROS costmap input for route-only recovery; never edits a received map."""
import math
import numpy as np
from rclpy.time import Time
from tf2_ros import TransformException
from multi_robot_exploration.observations import project_local_navigation
from seed_bridge import seed_bridge


def yaw(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))


def receive_costmap(node, message, robot):
    # Installed only for a bridge-enabled system. Existing allocation lock gives
    # one consistent message/receipt snapshot to each joint decision.
    with node.lock:
        node.navigation_costmaps[robot]=(message,node.now())


def self_body_exclusions(shared_cells, own, navigation, resolution, origin, pose):
    rows,columns=np.indices(shared_cells.shape)
    x=origin[0]+(columns+.5)*resolution;y=origin[1]+(rows+.5)*resolution
    return ((x-pose[0])**2+(y-pose[1])**2<=.25**2)&(shared_cells==100)&(own==0)&(navigation>=0)&(navigation<99)


def connect_seed(node, robot, shared, own, shared_inflated, own_inflated, seed, routing_shared_cells=None):
    now=node.now()
    record=dict(kind='gz01_seed_connection',sim=now,robot=robot,
                decision_id=node.allocator.decision_id,shared_version=shared['version'])
    def reject(reason,**facts):
        node.record(dict(record,reason=reason,**facts));return None
    entry=node.navigation_costmaps.get(robot)
    if entry is None:return reject('missing_costmap')
    grid,received=entry
    generated=grid.header.stamp.sec+grid.header.stamp.nanosec*1e-9
    source_age,receipt_age=now-generated,now-received
    record.update(source_stamp=generated,receipt_stamp=received,
                  source_age_s=source_age,receipt_age_s=receipt_age,frame=grid.header.frame_id)
    # A just-delivered old costmap is not fresh. Source and receipt clocks must
    # both be current, and the transform is evaluated at that source time.
    if not (0<=source_age<=1. and 0<=receipt_age<=1.):
        return reject('stale_or_future_costmap')
    try:
        stamped=node.tf[robot].lookup_transform(grid.header.frame_id,'merge_map',
                                               Time.from_msg(grid.header.stamp))
    except TransformException as error:
        return reject('costmap_source_time_TF_unavailable',error=str(error))
    transform=stamped.transform;origin=grid.info.origin
    projected=project_local_navigation(
        np.asarray(grid.data).reshape(grid.info.height,grid.info.width),grid.info.resolution,
        (origin.position.x,origin.position.y,yaw(origin.orientation)),
        (transform.translation.x,transform.translation.y,yaw(transform.rotation)),shared)
    pose=node.allocator.robots[robot].pose
    if routing_shared_cells is not None:
        excluded=self_body_exclusions(shared['cells'],own,projected,shared['resolution'],shared['origin'],pose)
        routing_shared_cells[excluded]=0
        record.update(self_body_route_contract='knownfree-source-time-Nav2-self-exclusion-v1',
            self_body_radius_m=.25,self_body_excluded_cells=np.argwhere(excluded).tolist(),
            self_body_excluded_raw_occupied_count=int(excluded.sum()),original_map_modified=False)
    peers=[r.pose for name,r in node.allocator.robots.items() if name!=robot]
    connection,facts=seed_bridge(shared['cells'],own,shared_inflated,own_inflated,
        projected,seed,shared['resolution'],max(source_age,receipt_age),shared['origin'],pose,peers,
        peer_clearance=.55 if node.system_variant=='peer-compact-v1' else .70,
        allow_soft_cost=node.system_variant=='peer-compact-v1')
    node.record(dict(record,local_from_shared=[transform.translation.x,transform.translation.y,
        yaw(transform.rotation)],connection_cells=connection,**facts))
    return connection
