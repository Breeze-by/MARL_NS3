"""A0 candidate clearance against fresh Navigation2 plans of currently owned goals."""
import math
import os

from nav_msgs.msg import Path
from rclpy.time import Time
from tf2_ros import TransformException

from multi_robot_exploration.allocation import route_prefix, route_separation
from shared_navigation_map import ACTIVE_ROUTE_VERSION


MAX_AGE_NS = 2_000_000_000


def remaining_plan(points, pose):
    nearest = min(range(len(points)), key=lambda index: math.dist(points[index], pose))
    return (pose, *points[nearest:])


def install_active_route_guard(node, planner_tolerance):
    allocator = node.allocator
    prefix_length, separation = allocator.initial_route_conflicts
    plans, accepted = {}, {}
    topics = {robot: f'/{robot}/plan' for robot in allocator.robots}

    def receive(message, robot):
        with node.lock:
            plans[robot] = message

    def goal_accepted(event):
        robot = event['robot']
        key = (event['token'], event['uuid'])
        request = node._nav2_goal_guard.requests.get(robot)
        if request is not None and key == (request['token'], request['uuid']):
            accepted[robot] = (key, node.get_clock().now().nanoseconds)
            plans.pop(robot, None)

    def prepare():
        if not node.shared_navigation_map_active:
            return None
        now = node.get_clock().now().nanoseconds
        paths, sources = {}, {}
        for robot, state in allocator.robots.items():
            if state.state != 'active' or state.pose is None or not 0 <= now / 1e9 - state.stamp <= MAX_AGE_NS / 1e9:
                continue
            owner = accepted.get(robot)
            request = node._nav2_goal_guard.requests.get(robot)
            plan = plans.get(robot)
            key = (state.token, state.uuid)
            if (owner is None or owner[0] != key or request is None
                    or (request['token'], request['uuid']) != key or plan is None
                    or plan.header.frame_id != request['frame'] or not plan.poses):
                continue
            stamp = Time.from_msg(plan.header.stamp)
            # Path has no UUID. Use the real owner, acceptance time, endpoint
            # tolerance and source freshness together to associate provenance.
            if stamp.nanoseconds < owner[1] or not 0 <= now - stamp.nanoseconds <= MAX_AGE_NS:
                continue
            points = tuple((pose.pose.position.x, pose.pose.position.y) for pose in plan.poses)
            if math.dist(request['xy'], points[-1]) > planner_tolerance:
                continue
            try:
                transform = node.tf[robot].lookup_transform('merge_map', plan.header.frame_id, stamp).transform
            except TransformException:
                continue
            rotation = transform.rotation
            yaw = math.atan2(2 * (rotation.w * rotation.z + rotation.x * rotation.y),
                             1 - 2 * (rotation.y ** 2 + rotation.z ** 2))
            cosine, sine = math.cos(yaw), math.sin(yaw)
            tx, ty = transform.translation.x, transform.translation.y
            common = tuple((tx + cosine * x - sine * y, ty + sine * x + cosine * y) for x, y in points)
            paths[robot] = remaining_plan(common, state.pose[:2])
            sources[robot] = dict(token=key[0], uuid=key[1], accepted_sim_ns=owner[1],
                                  plan_sim_ns=stamp.nanoseconds, remaining_points=len(paths[robot]))

        decision_id = allocator.decision_id
        node.record(dict(kind='active_route_guard_snapshot', sim=node.now(),
                         snapshot_sim_ns=now, decision_id=decision_id, plans=sources))
        if not paths:
            return None

        def admit(candidate, route):
            prefix = route_prefix(route, prefix_length)
            distances = {peer: route_separation(prefix, plan) for peer, plan in paths.items()}
            conflicts = [peer for peer, distance in distances.items() if distance < separation]
            node.record(dict(kind='active_route_guard_candidate', sim=node.now(), decision_id=decision_id,
                robot=candidate['robot'], target=candidate['position'], checked_peers=list(distances),
                minimum_separation_m=min(distances.values()), separation_by_peer_m=distances,
                conflicting_peers=conflicts, admitted=not conflicts))
            return not conflicts

        return admit

    for robot, topic in topics.items():
        node.subscriptions_kept.append(node.create_subscription(
            Path, topic, lambda message, robot=robot: receive(message, robot), 1))
    node._observe_active_route_goal_accepted = goal_accepted
    allocator.active_route_guard = prepare
    node.record(dict(kind='active_route_guard_applied', sim=node.now(), pid=os.getpid(),
        revision=ACTIVE_ROUTE_VERSION, topics=topics, prefix_length_m=prefix_length,
        separation_m=separation, plan_max_age_ns=MAX_AGE_NS, pose_max_age_ns=MAX_AGE_NS,
        planner_endpoint_tolerance_m=planner_tolerance))
