"""GZ-01 common joint execution; no Node, model load or forward at import."""
import argparse
import json
from pathlib import Path
import sys
import time
import numpy as np
from system_variants import GOAL_SEPARATION_M
from seed_connection_ros import receive_costmap, connect_seed
from nav_msgs.msg import OccupancyGrid
from rclpy.qos import QoSProfile, DurabilityPolicy
from std_msgs.msg import String
from peer_keepout import target_allowed, route_blocked

WORKSPACE = Path(__file__).resolve().parent.parent
# Import the accepted RL04 adapter first, so its existing module/path bindings
# and complete selected-parent/checkpoint/ROI validation remain unchanged.
sys.path.insert(0, str(WORKSPACE/'rl04'))
from ros_headquarters import RL04Headquarters, close_controller
from ros_policy import CheckpointHeadquarters
from diagnose import observed_row
from multi_robot_exploration.joint import JointTraditionalPolicy, slot_mask, choice_to_slot, _base_slot_mask
from multi_robot_exploration.ppo import encode
from multi_robot_exploration.rl_ledger import Ledger
import rclpy
from rclpy.signals import SignalHandlerOptions
from rclpy.executors import ExternalShutdownException

EXECUTION = dict(version='gz01-common-600sim-130joint-v1',
                 step_sim_seconds=5., episode_decisions=130)


class PolicyTrace:
    """Record the same actual policy invocation; never perform an extra NN pass."""
    def __init__(self, policy, node, directory, arm):
        self.policy, self.node, self.directory, self.arm = policy, node, directory, arm
        directory.mkdir(exist_ok=False)
        self.calls = 0
        self.forward_output = None
        if arm == 'rl':
            self.hook = policy.model.register_forward_hook(self.capture_forward)

    def capture_forward(self, module, inputs, output):
        self.forward_output = tuple(value.detach().cpu().numpy().copy() for value in output)

    def select(self, observation):
        self.calls += 1
        self.forward_output = None
        before_sim, before_wall, before_ns = self.node.now(), time.monotonic(), time.time_ns()
        if self.arm == 'rl':
            # Use the loader's original ActorCritic instance and act implementation.
            # Its old recorder wrapper is deliberately bypassed to avoid double IO.
            record = self.policy.model.act(observation, deterministic=True)
            action = record['action']
            encoded, masks, slots = record['inputs'], record['masks'], record['slots']
        else:
            action = self.policy.select(observation)
            encoded = encode(observation, self.node.config['task_roi'])
            masks = np.stack([slot_mask(observation, i, action.choices[:i]) for i in range(3)])
            slots = np.array([choice_to_slot(c) for c in action.choices])
        completed_ns, completed_wall, completed_sim = time.time_ns(), time.monotonic(), self.node.now()
        path = self.directory/f'{self.calls:04d}.npz'
        payload = dict(encoded_inputs=encoded, conditional_masks=masks, slots=slots,
            received_shared_cells=observation['map']['cells'],
            received_origin=observation['map']['origin'], received_resolution=observation['map']['resolution'],
            model_output_available=np.array(self.arm=='rl'),
            raw_logits=self.forward_output[0] if self.arm=='rl' else np.empty((0,3,17)),
            raw_value=self.forward_output[1] if self.arm=='rl' else np.empty((0,)))
        for robot, message in self.node.local_maps.items():
            payload[robot+'_local_cells'] = np.asarray(message.data, dtype=np.int8).reshape(message.info.height,message.info.width)
            payload[robot+'_local_origin'] = [message.info.origin.position.x,message.info.origin.position.y]
            payload[robot+'_local_resolution'] = message.info.resolution
            payload[robot+'_local_header_stamp'] = [message.header.stamp.sec,message.header.stamp.nanosec]
        np.savez_compressed(path, **payload)
        event = dict(kind='rl_real_inference' if self.arm=='rl' else 'traditional_real_decision',
            sim=completed_sim,arm=self.arm,sequence=self.calls,policy_start_sim=before_sim,
            policy_wall_s=completed_wall-before_wall,decision_id=action.decision_id,
            observed_state_and_candidates=observed_row(observation),choices=action.choices,
            raw_choices=action.choices,input_npz=str(path),
            evidence_io_wall_s=(time.time_ns()-completed_ns)/1e9,
            raw_frontier_reconstruction='offline from saved received grids; unavailable before candidate filters',
            nn_forward_expected=int(self.arm=='rl'),physical_stop_verified=False)
        if self.arm == 'rl':
            event.update(inference_start_sim=before_sim,inference_wall_ns=before_ns,
                inference_wall_s=(completed_ns-before_ns)/1e9,inference_sequence=self.calls,
                value=record['value'],logprob=record['logprob'],entropy=record['entropy'],
                conditional_options=record['masks'].sum(axis=1))
        if observation.get('joint_assignment_rule')=='maximum-participation-v1':
            event.update(joint_assignment_rule=observation['joint_assignment_rule'],
                original_conditional_masks=np.stack([_base_slot_mask(observation,i,action.choices[:i]) for i in range(3)]),
                actual_conditional_masks=masks)
        self.node.record(event)
        return action


class GZHeadquarters(RL04Headquarters):
    def __init__(self, checkpoint, expected_sha256, directory, ledger, arm, timed=True,
                 system_variant='reference-v1',joint_participation=False):
        self.arm = arm
        self.joint_participation=joint_participation
        self.system_variant = system_variant
        self.peer_keepout_state = None
        super().__init__(checkpoint, expected_sha256, directory, ledger, timed=timed)
        self.allocator.goal_separation_m = GOAL_SEPARATION_M[system_variant]
        if system_variant in ('idle-body-guard-v1','peer-compact-v1'):
            self.allocator.idle_body_goal_clearance_m = (.30 if system_variant=='peer-compact-v1' else .70) + self.config['backend']['xy_goal_tolerance_m']
        if system_variant in ('seed-connection-v1','idle-body-guard-v1','peer-compact-v1'):
            self.navigation_costmaps = {}
            self.allocator.seed_connection = lambda *args,**kwargs: connect_seed(self, *args,**kwargs)
            costmap_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
            self.subscriptions_kept += [self.create_subscription(OccupancyGrid,
                f'/{robot}/local_costmap/costmap',
                lambda message, r=robot: receive_costmap(self, message, r), costmap_qos)
                for robot in self.tf]
        if system_variant == 'peer-compact-v1':
            self.allocator.self_body_route_exclusion=True
            self.allocator.planner_goal_admissibility=True
            if joint_participation:self.allocator.initial_route_conflicts=(.26*1.7,.55)
            self.allocator.peer_routing_mask=self.peer_route_mask
            self.allocator.peer_goal_valid=lambda robot,target:target_allowed(
                robot,target,self.peer_keepout_state,self.now())
            self.subscriptions_kept.append(self.create_subscription(String,
                '/peer_keepout_state',self.receive_peer_state,1))
        if self.config['step_sim_seconds'] != EXECUTION['step_sim_seconds']:
            raise ValueError('GZ-01 requires the original 5sim joint schedule')
        checkpoint_decisions = self.config['episode_decisions']
        self.config = dict(self.config, episode_decisions=EXECUTION['episode_decisions'])
        policy = self.policy if arm == 'rl' else JointTraditionalPolicy()
        self.policy = PolicyTrace(policy, self, directory/'policy-trace', arm)
        self.record(dict(kind='gz01_common_execution_bound',sim=self.now(),arm=arm,
            execution=EXECUTION,checkpoint_episode_decisions=checkpoint_decisions,
            checkpoint_unchanged=True,natural_completion_rule=None,
            traditional_postselection_rejections_preserved=True,
            system_variant=system_variant,goal_separation_m=self.allocator.goal_separation_m,
            planner_goal_bounds='navfn-round-and-own-floor-v1' if self.allocator.planner_goal_admissibility else None,
            self_body_route_contract='knownfree-source-time-Nav2-self-exclusion-v1' if self.allocator.self_body_route_exclusion else None,
            joint_assignment_rule='maximum-participation-v1' if joint_participation else None,
            initial_route_rule='first-idle-prefix-v1' if self.allocator.initial_route_conflicts else None,
            initial_route_limits=self.allocator.initial_route_conflicts,
            task_end_tolerance_m=self.config['backend']['xy_goal_tolerance_m'],
            guard_centre_separation_m=.30,
            guard_scope='followup02 unified .30m centre monitoring, not historical .70m runs',
            idle_body_goal_clearance_m=self.allocator.idle_body_goal_clearance_m,
            seed_connection_enabled=system_variant in ('seed-connection-v1','idle-body-guard-v1','peer-compact-v1'),
            peer_keepout_enabled=system_variant=='peer-compact-v1',
            limitation='Actual path safety requires measured Nav2/peer-mask validation; no formal dynamic guarantee'))

    def peer_route_mask(self, robot, shared):
        state=self.peer_keepout_state
        now=self.now()
        mask=route_blocked(robot,shared,state,now)
        self.record(dict(kind='gz01_peer_routing_mask',sim=now,robot=robot,
            decision_id=self.allocator.decision_id,shared_version=shared['version'],
            peer_sequence=None if state is None else state['sequence'],
            peer_generated_sim=None if state is None else state['generated_sim'],
            blocked_cells=int(np.count_nonzero(mask))))
        return mask

    def receive_peer_state(self,message):
        with self.lock:
            self.peer_keepout_state=json.loads(message.data)
            self.record(dict(kind='gz01_peer_state_received',sim=self.now(),
                sequence=self.peer_keepout_state['sequence'],generated_sim=self.peer_keepout_state['generated_sim'],
                received_monotonic=time.monotonic(),odom_stamps=self.peer_keepout_state['odom_stamps'],
                correction_stamps=self.peer_keepout_state['correction_stamps']))

    def nav_goal_in_local_map(self,robot,x,y):
        return super().nav_goal_in_local_map(robot,x,y,
            planner_bounds=self.system_variant=='peer-compact-v1')

    def goal_valid(self,robot,x,y):
        if self.system_variant=='peer-compact-v1' and not target_allowed(
                robot,(x,y),self.peer_keepout_state,self.now()):return False
        return super().goal_valid(robot,x,y)

    def allocate_common(self):
        """Same immutable snapshot → PPO → common gate → inherited Nav2 pipeline."""
        with self.ledger.call('ros_joint_decision_attempt'):
            with self.lock:
                self.allocator.tick(self.now())
                if self.allocator.halted:
                    return dict(state='halted', proposals={}, rejected={})
                if self.decisions >= self.config['episode_decisions']:
                    self.halt('decision_budget')
                    return dict(state='decision_budget', proposals={}, rejected={})
                missing=[r.name for r in self.allocator.robots.values() if r.pose is None]
                if self.allocator.map is None or missing:
                    self.record(dict(kind='rl_wait_observation',sim=self.now(),missing_map=self.allocator.map is None,
                        missing_robots=missing,pose_tf_errors=self.pose_tf_errors))
                    self.dispatch_requested_cancels()
                    return dict(state='awaiting_observation', proposals={}, rejected={})
                # Explicit engineering guard for missing/frozen ROS delivery; no
                # replacement goal or modified checkpoint is used on stale state.
                if any(self.now()-r.stamp > 2. for r in self.allocator.robots.values()):
                    self.record(dict(kind='rl_wait_fresh_state', sim=self.now(),
                        pose_ages_s={r.name:self.now()-r.stamp for r in self.allocator.robots.values()},
                        pose_tf_errors=self.pose_tf_errors))
                    self.dispatch_requested_cancels()
                    return dict(state='awaiting_fresh_state', proposals={}, rejected={})
                observation = self.allocator.get_observation()
                if self.joint_participation:
                    observation=dict(observation,joint_assignment_rule='maximum-participation-v1')
                self.ledger.add('ros_allocator_observation_build')
                action = self.policy.select(observation)
                proposals, rejected = self.allocator.apply(observation, action)
                self.decisions += 1
                self.record(dict(kind='rl_joint_action', sim=self.now(), decision=self.decisions,
                                 decision_id=action.decision_id, map_version=action.map_version,
                                 choices=action.choices, rejected=rejected))
                if rejected and self.arm == 'rl':
                    raise ValueError('PPO joint action rejected: '+str(rejected))
                self.dispatch_requested_cancels()
            for robot, (target, token) in proposals.items():
                self.send_goal(robot, target, token)
            return dict(state='applied', proposals=proposals, rejected=rejected, action=action)

    def allocate_once(self):
        # Use exactly the same observation/gates/allocator/Nav2 path for both
        # arms; original traditional post-selection invalidity is an outcome.
        started, begin_sim = time.monotonic(), self.now()
        self.allocation_attempts += 1
        result = self.allocate_common()
        self.record(dict(kind='gz01_allocation_wall',sim=self.now(),
            allocation_attempt=self.allocation_attempts,allocation_start_sim=begin_sim,
            allocation_wall_s=time.monotonic()-started,state=result['state'],
            pose_tf_errors=self.pose_tf_errors,decision_id=self.allocator.decision_id))
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--checkpoint-sha256', required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--arm', choices=('rl','traditional'), required=True)
    parser.add_argument('--system-variant',choices=tuple(GOAL_SEPARATION_M),default='reference-v1')
    parser.add_argument('--joint-participation',action='store_true')
    args, ros_args = parser.parse_known_args()
    args.run_dir.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(args.run_dir/'ledger.jsonl', 'gz01_real_ros_'+args.arm)
    rclpy.init(args=ros_args, signal_handler_options=SignalHandlerOptions.NO)
    node = GZHeadquarters(args.checkpoint,args.checkpoint_sha256,args.run_dir,ledger,args.arm,
                         system_variant=args.system_variant,joint_participation=args.joint_participation)
    try:
        rclpy.spin(node)
        if node.worker_error:
            raise RuntimeError(node.worker_error)
    except KeyboardInterrupt:
        pass
    except ExternalShutdownException as error:
        if node.worker_error:
            raise RuntimeError(node.worker_error) from error
        raise
    finally:
        close_controller(node,ledger)


if __name__ == '__main__':
    main()
