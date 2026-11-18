"""Literal ROS-direct navigation maps made from the three received SLAM grids."""
import json
import math
import os
from pathlib import Path
import sys


VERSION = 'a0-shared-navigation-map-v1'
STAGED_VERSION = 'a0-shared-navigation-after-first-success-v2'
ACTIVE_ROUTE_VERSION = 'a0-shared-navigation-active-route-v3'
VERSIONS = (VERSION, STAGED_VERSION, ACTIVE_ROUTE_VERSION)
ENV = 'NET01_NAVIGATION_SHARED_MAP_REVISION'
SEED_ROUTE_ENV = 'NET01_NAVIGATION_SEED_ROUTE_REVISION'
SEED_ROUTE_VERSION = 'a0-approved-shared-seed-route-v1'
ACTIVATION_TOPIC = '/shared_navigation/activate'
# The A0 SLAM publishers have a nominal 1.25sim-second grid cadence under the
# reviewed 0.25 RTF. A snapshot represents three sources, with distinct phases.
MAX_SOURCE_AGE_SIM_S = 4.0
ROBOTS = ('tb1', 'tb2', 'tb3')


def selected(environment):
    revision = environment.get(ENV)
    if revision and (revision not in VERSIONS or environment.get('NET01_DIRECT_REFERENCE') != '1'):
        raise ValueError('Shared navigation maps require the explicit literal A0 revision')
    return revision


def topic(robot):
    return f'/{robot}/shared_navigation/map'


def stamp(grid):
    return grid.header.stamp.sec + grid.header.stamp.nanosec / 1e9


def load_stamp_ns(grid):
    value = grid.info.map_load_time
    return value.sec * 1_000_000_000 + value.nanosec


def robot_navigation_map(grids, calibrations, receiver, merge_maps):
    """Fuse directly in the destination map frame on the receiver's SLAM lattice."""
    tx, ty, yaw = calibrations[receiver]
    origin = grids[receiver].info.origin.position
    cos, sin = math.cos(yaw), math.sin(yaw)
    poses = []
    for x, y, heading in calibrations:
        dx, dy = x - tx, y - ty
        poses.append((cos * dx + sin * dy - origin.x,
                      -sin * dx + cos * dy - origin.y, heading - yaw))
    merged = merge_maps(grids, 'map', poses, grids[receiver].info.resolution)
    merged.info.origin.position.x += origin.x
    merged.info.origin.position.y += origin.y
    return merged


def apply_static_topic(parameters, robot):
    values = parameters['global_costmap']['global_costmap']['ros__parameters']
    if (values['global_frame'] != 'map' or values['map_topic'] != f'/{robot}/map'
            or 'static_layer' not in values['plugins']
            or not values['static_layer']['map_subscribe_transient_local']):
        raise ValueError('Shared navigation needs the reviewed robot-map global StaticLayer')
    values['map_topic'] = topic(robot)


def goal_map_evidence(node, event):
    from nav2_goal_guard import costmap_floor_cell

    robot = event['robot']
    request_xy = event['actual_goal_position'][:2]
    own = node.local_maps[robot]
    if not node.shared_navigation_map_active:
        return dict(phase='own_slam', source=f'/{robot}/map',
            own_slam_cell=costmap_floor_cell(own, *request_xy), own_slam_stamp=stamp(own))
    grid = node.shared_navigation_maps[robot]
    return dict(phase='shared_navigation', source=topic(robot), map_stamp=stamp(grid),
        map_load_sim_ns=load_stamp_ns(grid),
        shared_navigation_cell=costmap_floor_cell(grid, *request_xy),
        own_slam_cell=costmap_floor_cell(own, *request_xy), own_slam_stamp=stamp(own))


def install_hq(node, revision):
    """Use the same static-map input for route and goal checks; keep raw SLAM separately."""
    import numpy as np
    from nav_msgs.msg import OccupancyGrid
    from rclpy.qos import QoSProfile, DurabilityPolicy
    from rclpy.time import Time
    from std_msgs.msg import String
    from tf2_ros import TransformException
    from multi_robot_exploration import frontier
    from multi_robot_exploration.observations import project_local_navigation

    node.shared_navigation_maps = {}
    node.shared_navigation_map_active = False
    original_seed = node.allocator.seed_connection
    staged = revision != VERSION
    seed_options = ({'use_approved_shared_route': True}
                    if revision == ACTIVE_ROUTE_VERSION and os.environ.get(SEED_ROUTE_ENV) == SEED_ROUTE_VERSION
                    else {})
    activation = None
    latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)

    if staged:
        first_successes = {}
        trigger = node.create_publisher(String, ACTIVATION_TOPIC, latched)

        def observe_terminal(event):
            nonlocal activation
            if activation is not None or event['status'] != 'succeeded' or not event['uuid']:
                return
            robot = event['robot']
            first_successes.setdefault(robot, {key: event[key] for key in ('token', 'uuid', 'sim')})
            if set(first_successes) == set(ROBOTS):
                activation = node.get_clock().now().nanoseconds
                payload = dict(activation_sim_ns=activation, first_successes=first_successes)
                trigger.publish(String(data=json.dumps(payload)))
                node.record(dict(kind='shared_navigation_activation_requested', sim=node.now(), **payload))

        node._observe_shared_navigation_terminal = observe_terminal

    def receive(message, robot):
        # Raw SLAM grids are relayed unchanged during dispersal; their
        # map_load_time is unset. Fused grids record the new map's load time.
        if staged and (activation is None or load_stamp_ns(message) != activation):
            return
        if message.header.frame_id != 'map' or message.info.origin.orientation.w != 1.0:
            raise ValueError('Expected an axis-aligned shared navigation map in the robot map frame')
        with node.lock:
            node.shared_navigation_maps[robot] = message
            if node.shared_navigation_map_active:
                node._nav2_goal_guard.map_received(message, robot, shared=True)
            elif len(node.shared_navigation_maps) == len(ROBOTS):
                enable()
                node.record(dict(kind='shared_navigation_map_activated', sim=node.now(),
                    activation_sim_ns=activation, robot_map_stamps={
                        name: stamp(grid) for name,grid in node.shared_navigation_maps.items()}))
                for name,grid in node.shared_navigation_maps.items():
                    node._nav2_goal_guard.map_received(grid, name, shared=True)

    def navigation_grid(robot, shared):
        grid = node.shared_navigation_maps.get(robot)
        if grid is None or not 0 <= node.now() - stamp(grid) <= MAX_SOURCE_AGE_SIM_S:
            return None
        try:
            stamped = node.tf[robot].lookup_transform('map', 'merge_map', Time())
        except TransformException:
            return None
        transform = stamped.transform
        q = transform.rotation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        origin = grid.info.origin.position
        local_from_shared = (transform.translation.x, transform.translation.y, yaw)
        projected = project_local_navigation(
            np.asarray(grid.data).reshape(grid.info.height, grid.info.width),
            grid.info.resolution, (origin.x, origin.y, 0.0), local_from_shared, shared)
        node.record(dict(kind='shared_navigation_grid', sim=node.now(), robot=robot,
            source=topic(robot), frame=grid.header.frame_id, map_stamp=stamp(grid),
            shared_version=shared['version'], local_from_shared=local_from_shared,
            resolution=grid.info.resolution, shape=[grid.info.height, grid.info.width],
            known_free_cells=int(np.count_nonzero(projected == 0))))
        return projected

    def seed_connection(robot, shared, navigation, shared_inflated, navigation_inflated,
                        seed, routing_shared_cells=None):
        own = node.local_navigation_grid(robot, shared)
        if own is None:
            return None
        height, width = own.shape
        own_inflated = frontier.costmap(own, width, height, shared['resolution'])
        # Keep original own-map evidence for any route-only exemption. The
        # shared navigation map may only tighten it when it reports occupancy.
        own = np.where(navigation > 0, navigation, own)
        inflated = np.where(navigation_inflated > 0, navigation_inflated, own_inflated)
        return original_seed(robot, shared, own, shared_inflated, inflated,
                             seed, routing_shared_cells=routing_shared_cells, **seed_options)

    def enable():
        node.allocator.local_navigation_grid = navigation_grid
        if original_seed is not None:
            node.allocator.seed_connection = seed_connection
        node.shared_navigation_map_active = True

    for robot in ROBOTS:
        node.subscriptions_kept.append(node.create_subscription(OccupancyGrid,
            topic(robot), lambda message, robot=robot: receive(message, robot), latched))
    if not staged:
        enable()
    node.record(dict(kind='shared_navigation_map_applied', sim=node.now(), pid=os.getpid(),
        revision=revision, topics={robot: topic(robot) for robot in ROBOTS},
        initial_phase='own_slam' if staged else 'shared_navigation',
        maximum_source_age_sim_s=MAX_SOURCE_AGE_SIM_S, own_seed_evidence_preserved=True,
        **({'navigation_seed_route_revision': SEED_ROUTE_VERSION} if seed_options else {})))


def main():
    revision = selected(os.environ)
    if not revision:
        raise ValueError('A0 shared map publisher requires its explicit revision')
    staged = revision != VERSION
    import rclpy
    from nav_msgs.msg import OccupancyGrid
    from rclpy.qos import QoSProfile, DurabilityPolicy
    from std_msgs.msg import String

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent /
                           'workspace/src/merge_map/merge_map'))
    from merge_map import MergeMapNode, merge_maps

    class SharedNavigationMerge(MergeMapNode):
        def __init__(self):
            super().__init__()
            qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
            self.navigation = [self.create_publisher(OccupancyGrid, topic(robot), qos)
                               for robot in ROBOTS]
            self.trace = (Path(os.environ['BASE01_RUN_DIR']) /
                          'shared-navigation-map-publication.jsonl').open('x', buffering=1)
            self.activation = None
            self.fused = False
            if staged:
                self.trigger = self.create_subscription(String, ACTIVATION_TOPIC, self.activate, qos)

        def activate(self, message):
            if self.activation is None:
                payload = json.loads(message.data)
                self.activation = payload['activation_sim_ns']
                self.trace.write(json.dumps(dict(pid=os.getpid(), kind='activation_received',
                    sim=self.get_clock().now().nanoseconds / 1e9, **payload)) + '\n')
                self.publish_shared_navigation()

        def map_callback(self, message, index):
            if staged and not self.fused:
                self.publish_navigation(index, message, 'own_slam',
                    {ROBOTS[index]: stamp(message)})
            super().map_callback(message, index)

        def try_merge_and_publish(self):
            super().try_merge_and_publish()
            self.publish_shared_navigation()

        def publish_shared_navigation(self):
            if staged and self.activation is None:
                return
            if not all(self.maps):
                return
            now = self.get_clock().now().nanoseconds / 1e9
            stamps = [stamp(grid) for grid in self.maps]
            if any(not 0 <= now - value <= MAX_SOURCE_AGE_SIM_S for value in stamps):
                return
            for index in range(len(ROBOTS)):
                grid = robot_navigation_map(self.maps, self.map_poses, index, merge_maps)
                if staged:
                    grid.info.map_load_time.sec, grid.info.map_load_time.nanosec = divmod(
                        self.activation, 1_000_000_000)
                self.publish_navigation(index, grid, 'shared_navigation', dict(zip(ROBOTS, stamps)))
            self.fused = True

        def publish_navigation(self, index, grid, phase, sources):
            publisher = self.navigation[index]
            publisher.publish(grid)
            self.trace.write(json.dumps(dict(pid=os.getpid(), topic=publisher.topic_name,
                phase=phase, map_load_sim_ns=load_stamp_ns(grid),
                sim=self.get_clock().now().nanoseconds / 1e9, source_stamps=sources,
                map_stamp=stamp(grid), origin=[grid.info.origin.position.x, grid.info.origin.position.y],
                width=grid.info.width, height=grid.info.height, resolution=grid.info.resolution)) + '\n')

        def destroy_node(self):
            self.trace.close()
            return super().destroy_node()

    rclpy.init()
    node = SharedNavigationMerge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
