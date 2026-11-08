"""RL02 loader and real input/Action tracing over the accepted ROS execution."""
import argparse
import json
from pathlib import Path
import sys
import time
import uuid
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
PROJECT = WORKSPACE.parent
sys.path.insert(0, str(WORKSPACE/'rl01'))
from ros_policy import CheckpointHeadquarters
import rclpy
from rclpy.action import ActionClient
from rclpy.signals import SignalHandlerOptions
from rclpy.executors import ExternalShutdownException
from unique_identifier_msgs.msg import UUID
from diagnose import observed_row, plain
from maps import sha, dump
from train import validate_checkpoint
from multi_robot_exploration.ppo import ActorCritic, load_checkpoint
from multi_robot_exploration.rl_ledger import Ledger


class RecordedPolicy:
    def __init__(self, model, directory, node):
        self.model, self.directory, self.node = model, directory, node
        directory.mkdir(exist_ok=False)
        self.calls = 0

    def select(self, observation):
        before_ns, before_sim = time.time_ns(), self.node.now()
        record = self.model.act(observation, deterministic=True)
        completed_ns = time.time_ns()
        self.calls += 1
        path = self.directory/f'{self.calls:04d}.npz'
        np.savez_compressed(path, encoded_inputs=record['inputs'], conditional_masks=record['masks'],
            slots=record['slots'], received_shared_cells=observation['map']['cells'],
            received_origin=observation['map']['origin'], received_resolution=observation['map']['resolution'])
        self.node.record(dict(kind='rl_real_inference', sim=self.node.now(), inference_start_sim=before_sim,
            inference_wall_ns=before_ns, inference_wall_s=(completed_ns-before_ns)/1e9,
            evidence_io_wall_s=(time.time_ns()-completed_ns)/1e9,
            inference_sequence=self.calls, decision_id=record['action'].decision_id,
            raw_choices=record['action'].choices, value=record['value'], logprob=record['logprob'],
            entropy=record['entropy'], conditional_options=record['masks'].sum(axis=1),
            observed_state_and_candidates=observed_row(observation), input_npz=str(path),
            physical_stop_verified=False))
        return record['action']


class LoggedActionClient(ActionClient):
    def __init__(self, node, action_type, action_name):
        super().__init__(node, action_type, action_name)
        self.trace_node, self.trace_robot = node, action_name.split('/')[1]

    def send_goal_async(self, goal, feedback_callback=None, goal_uuid=None):
        node = self.trace_node
        state = node.allocator.robots[self.trace_robot]
        request_uuid = goal_uuid if goal_uuid is not None else UUID(uuid=list(uuid.uuid4().bytes))
        uuid_hex = bytes(request_uuid.uuid).hex()
        token = state.token
        node.request_uuids[(self.trace_robot, token)] = uuid_hex
        p, q = goal.pose.pose.position, goal.pose.pose.orientation
        node.record(dict(kind='rl_actual_nav2_goal_request', sim=node.now(), robot=self.trace_robot,
            token=token, request_uuid=uuid_hex, decision_id=node.allocator.decision_id,
            merge_map_target=state.target, actual_goal_frame=goal.pose.header.frame_id,
            actual_goal_stamp=goal.pose.header.stamp.sec+goal.pose.header.stamp.nanosec*1e-9,
            actual_goal_position=[p.x, p.y, p.z], actual_goal_quaternion=[q.x, q.y, q.z, q.w]))
        future = super().send_goal_async(goal, feedback_callback=feedback_callback, goal_uuid=request_uuid)
        def record_response(done):
            handle = done.result()
            node.record(dict(kind='rl_actual_nav2_goal_response', sim=node.now(), robot=self.trace_robot,
                token=token, request_uuid=uuid_hex, accepted=handle.accepted,
                accepted_uuid=bytes(handle.goal_id.uuid).hex() if handle.accepted else None))
        future.add_done_callback(record_response)
        return future


class RL02Headquarters(CheckpointHeadquarters):
    def __init__(self, checkpoint, expected_sha256, directory, ledger, timed=True):
        self.request_uuids = {}
        def loader(path, expected, activity):
            selection_path = PROJECT/'runs/selection.json'
            selected = json.loads(selection_path.read_text())['selected']
            relative = Path(selected['checkpoint'])
            if relative.parts[0] != 'rl-02':
                raise ValueError('Selected model is not an RL02 local artifact')
            bound = Path('/tmp/prior')/Path(*relative.parts[1:])
            if path.resolve() != bound.resolve() or sha(path) != expected or expected != selected['checkpoint_sha256']:
                raise ValueError('ROS selected checkpoint identity mismatch')
            parent = json.loads((path.parent/'summary.json').read_text())
            native = json.loads((path.parent/'process-exit.json').read_text())
            if native['exit_code'] != 0:
                raise ValueError('Selected ROS checkpoint parent did not exit0')
            actual = validate_checkpoint(path, parent)
            metadata = actual['metadata']
            if metadata['joint_decisions'] != selected['joint'] or metadata['run_number'] != selected['run']:
                raise ValueError('Selected checkpoint step/run identity was altered')
            torch.set_num_threads(1)
            model = ActorCritic(activity, metadata['config']['hidden'])
            load_checkpoint(path, model, restore_rng=False)
            config = metadata['config']
            if list(model.task_roi) != config['task_roi'] or config['task_roi'] != [-5.8, -5.6, 7.25, 5.3]:
                raise ValueError('ROS checkpoint observation ROI disagreement')
            if metadata.get('encoding') != 'received-grid-to-fixed-metric-roi-0.05m-v1':
                raise ValueError('ROS checkpoint observation encoding mismatch')
            model.eval()
            activity.flush('rl02_ros_model_bound', checkpoint=str(path), sha256=expected,
                selection_sha256=sha(selection_path), actual_checkpoint_joint=metadata['joint_decisions'],
                actual_checkpoint_adam_step=metadata['joint_decisions']//256*8,
                parent_run_completed_joint=parent['actual_joint_decisions'],
                p3_lock_sha256=metadata['p3_lock_sha256'], physical_stop_verified=False)
            return RecordedPolicy(model, directory/'inference', self), config

        super().__init__(checkpoint, expected_sha256, directory, ledger, timed=timed,
            policy_loader=loader, action_client_factory=LoggedActionClient)

    def goal_result_callback(self, robot, token, result):
        self.record(dict(kind='rl_actual_nav2_goal_result', sim=self.now(), robot=robot,
            token=token, request_uuid=self.request_uuids.get((robot,token)), raw_status=result.status))
        return super().goal_result_callback(robot, token, result)

    def record(self, event):
        # Evaluator consumes the same semantic events; the extra wall stamp
        # and trace events only make ROS delivery and Action linkage auditable.
        event = plain(event)
        event.setdefault('wall_ns', time.time_ns())
        super().record(event)


def close_controller(node, ledger):
    try:
        if rclpy.ok():
            node.halt('rl02_controller_shutdown')
        else:
            # decision_callback already halted before closing the context.
            # Do not issue another Action RPC on a closed ROS context.
            node.record(dict(kind='rl02_context_already_shutdown', sim=node.now(),
                first_worker_error=node.worker_error, physical_stop_verified=False))
    finally:
        node.events.close()
        node.destroy_node()
        ledger.flush('rl02_real_ros_end')
        if rclpy.ok():
            rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--checkpoint-sha256', required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    args, ros_args = parser.parse_known_args()
    args.run_dir.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(args.run_dir/'ledger.jsonl', 'rl02_real_ros_inference')
    # Same shutdown ordering as the accepted external supervisor: let Python
    # catch SIGINT while ROS remains alive for explicit halt/cancel requests.
    rclpy.init(args=ros_args, signal_handler_options=SignalHandlerOptions.NO)
    node = RL02Headquarters(args.checkpoint, args.checkpoint_sha256, args.run_dir, ledger)
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
        close_controller(node, ledger)


if __name__ == '__main__':
    main()
