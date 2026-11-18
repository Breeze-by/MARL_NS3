"""Opt-in owned Goal progress across Nav2 recovery; no new Node or motion goal."""
import math
import json
import os
import time
from pathlib import Path

VERSION = 'owned-goal-source-odom-progress-v1'
CONTRACT_FILE = 'config/NAVIGATION_PROGRESS_OWNED_GOAL_V1.json'


def load_contract(revision):
    if revision != VERSION:
        raise ValueError('Unknown explicit navigation progress revision')
    return json.loads((Path(__file__).resolve().parent/CONTRACT_FILE).read_text())



class NavProgressGuard:
    def __init__(self, node, contract):
        self.node, self.contract = node, dict(contract)
        self.directory = Path(node.events.name).parent
        self.window_ns = int(contract['window_sim_s'] * 1_000_000_000)
        self.radius = contract['required_movement_radius_m']
        self.max_gap_ns = 2_000_000_000  # Existing HQ pose freshness, not a new grace.
        self.anchors = {}
        self.last_source_ns = {}
        self.stalls = {}
        self.events = []
        self.real_terminal = None
        self.finished = False

    def record(self, kind, **fields):
        self.events.append(dict(kind=kind, monotonic_ns=time.monotonic_ns(), **fields))

    def odom_received(self, message, robot):
        node = self.node
        stamp_ns = message.header.stamp.sec*1_000_000_000 + message.header.stamp.nanosec
        frame = message.header.frame_id
        if not frame:
            return
        previous_ns = self.last_source_ns.get(robot)
        if previous_ns is not None and stamp_ns <= previous_ns:
            return  # Duplicate/old packets cannot reset a current or future Goal anchor.
        self.last_source_ns[robot] = stamp_ns
        state = node.allocator.robots[robot]
        uuid = state.uuid
        key = (robot, state.token, uuid)
        if (node.allocator.halted or state.state != 'active' or not uuid
                or node.request_uuids.get((robot, state.token)) != uuid
                or state.cancel_requested):
            return
        if node.now() - stamp_ns/1_000_000_000 > 2.0:
            previous_anchor = self.anchors.pop(robot, None)
            if previous_anchor is not None:
                self.record('progress_anchor_discarded', robot=robot, token=state.token,
                            uuid=uuid, source_odom_ns=stamp_ns,
                            reason='Original HQ one-sided source age exceeds 2sim')
            return  # Same cached-HQ-clock age rule; no new future-stamp test/AoI claim.
        position = message.pose.pose.position
        xy = (position.x, position.y)
        anchor = self.anchors.get(robot)
        if anchor is not None and anchor['key'] == key and stamp_ns <= anchor['last_ns']:
            return  # A duplicate/old packet must neither advance nor reset the anchor.
        reason = None
        if anchor is None or anchor['key'] != key:
            reason = 'first_valid_post_accept_odom'
        elif anchor['frame'] != frame:
            reason = 'odom_frame_changed'
        elif stamp_ns - anchor['last_ns'] > self.max_gap_ns:
            reason = 'source_sample_gap_exceeds_existing_pose_freshness'
        elif math.dist(xy, anchor['xy']) >= self.radius:
            reason = 'translation_progress'
        if reason is not None:
            self.anchors[robot] = dict(key=key, frame=frame, xy=xy,
                                      anchor_ns=stamp_ns, last_ns=stamp_ns)
            self.record('progress_anchor', robot=robot, token=state.token, uuid=uuid,
                        reason=reason, frame=frame, source_odom_ns=stamp_ns, xy=xy)
            return
        anchor['last_ns'] = stamp_ns
        if stamp_ns - anchor['anchor_ns'] < self.window_ns:
            return
        evidence = dict(robot=robot, token=state.token, uuid=uuid, frame=frame,
                        source_odom_ns=stamp_ns, anchor_ns=anchor['anchor_ns'],
                        anchor_xy=anchor['xy'], current_xy=xy,
                        displacement_m=math.dist(xy, anchor['xy']),
                        window_ns=self.window_ns, required_movement_radius_m=self.radius,
                        target=tuple(state.target))
        self.stalls[key] = evidence
        state.cancel_requested = True
        state.condition = 'source_odom_stall_cancel_required'
        self.record('stall_cancel_requested', **evidence)
        # Same original owned Cancel path; state stays active until real terminal.
        node.dispatch_requested_cancels()

    def finish(self, original, robot, token, status):
        state = self.node.allocator.robots[robot]
        key = (robot, token, state.uuid)
        target = state.target
        own_stall = (state.token == token and state.state == 'active'
                     and state.condition == 'source_odom_stall_cancel_required'
                     and not self.node.allocator.halted and key in self.stalls
                     and self.real_terminal == (robot, token, state.uuid, 5)
                     and status == 'canceled')
        completed = original(robot, token, status)
        if self.real_terminal is not None:
            self.record('real_terminal_finish', robot=robot, token=token,
                        observed_terminal=self.real_terminal, owned_uuid_before=key[2],
                        original_finish_returned=completed, original_status=status,
                        stall_marked=key in self.stalls,
                        allocator_halted=self.node.allocator.halted)
        if completed and own_stall:
            self.node.allocator.failed[robot].append(target)
            self.record('stall_failed_target_after_real_canceled',
                        robot=robot, token=token, uuid=key[2], target=target,
                        raw_nav2_status=5, high_level_status='canceled',
                        exclusion='Original per-robot failed-goal 0.2m exclusion')
        if completed:
            self.stalls.pop(key, None)
            if self.anchors.get(robot, {}).get('key') == key:
                self.anchors.pop(robot)
        return completed

    def finish_recording(self):
        if self.finished:
            return
        self.finished = True
        with (self.directory/'nav-progress-guard.json').open('x') as stream:
            json.dump(dict(contract=self.contract, pid=os.getpid(), events=self.events,
                           scope='Same-lock original pose replacement/source-stamp update, including inherited callback success returning None; source-header progress, cached HQ age gate; real Action terminal and original finish return. No generation AoI or truth input.'), stream, indent=2)



def install_nav_progress_guard(node, profile):
    contract = profile.get('nav_progress_guard')
    if contract is None:
        return None
    if contract['id'] != VERSION:
        raise ValueError('Unknown owned Goal progress contract')
    guard = NavProgressGuard(node, contract)
    original_odom = node.robot_odom_callback
    original_result = node.goal_result_callback
    original_finish = node.allocator.finish

    def odom(message, robot):
        with node.lock:
            before_pose = node.allocator.robots[robot].pose
            returned = original_odom(message, robot)
            state = node.allocator.robots[robot]
            source_stamp = message.header.stamp.sec + message.header.stamp.nanosec*1e-9
            if state.pose is not before_pose and state.stamp == source_stamp:
                # CheckpointHQ intentionally returns None even after original base True.
                # Observe the actual same-lock original update; do not repeat its TF work.
                guard.odom_received(message, robot)
            return returned

    def terminal(robot, token, result):
        with node.lock:
            state = node.allocator.robots[robot]
            previous = guard.real_terminal
            guard.real_terminal = (robot, token, state.uuid, result.status)
            try:
                return original_result(robot, token, result)
            finally:
                guard.real_terminal = previous

    node.robot_odom_callback = odom
    node.goal_result_callback = terminal
    node.allocator.finish = lambda robot, token, status: guard.finish(
        original_finish, robot, token, status)
    node._nav_progress_guard = guard
    return guard
