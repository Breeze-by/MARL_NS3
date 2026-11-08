"""Actual P7 timeout cancellation wiring, with Fake policy and typed futures only."""
import argparse
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import numpy as np
from rclpy.task import Future
from multi_robot_exploration.allocation import Allocator, JointAction, KEEP, WAIT
from multi_robot_exploration.rl_ledger import Ledger
from ros_policy import CheckpointHeadquarters
from mock_ros import MockHandle


def setup(ledger, pending=False):
    events = []
    allocator = Allocator(emit=events.append, task_timeout_s=90.)
    allocator.update_map(np.zeros((10, 10)), 1., (0., 0.), 91.)
    for name, pose in zip(allocator.robots, ((1., 1., 0.), (4., 4., 0.), (7., 7., 0.))):
        allocator.update_robot(name, pose, 91., (0., 0., 0.))
    robot = allocator.robots['tb1']
    robot.state, robot.token, robot.target, robot.started = ('pending' if pending else 'active'), 1, (2., 1.), 0.
    robot.uuid = None if pending else 'controlled-uuid'
    fake = SimpleNamespace(lock=threading.RLock(), ledger=ledger, allocator=allocator,
        config=dict(episode_decisions=100), decisions=0, goal_handles={}, timeout_cancel_tokens=set(),
        now=lambda: 91., record=events.append, get_logger=lambda: SimpleNamespace(info=lambda message: None))
    fake.mark_timeout_cancel = lambda name, token: CheckpointHeadquarters.mark_timeout_cancel(fake, name, token)
    fake.goal_result_callback = lambda name, token, result: CheckpointHeadquarters.goal_result_callback(fake, name, token, result)
    def choose(observation):
        ledger.add('controlled_non_neural_policy_select')
        return JointAction(observation['decision_id'], observation['map_version'], (KEEP, WAIT, WAIT))
    fake.policy = SimpleNamespace(select=choose)
    return fake, events


def run(directory):
    directory.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(directory/'ledger.jsonl', 'directed_timeout_wiring_fixture')
    results = {}
    # Real allocate_once marks the timeout cause before dispatching cancel.
    fake, events = setup(ledger)
    handle = MockHandle('tb1', 1, ledger)
    handle.get_result_async().add_done_callback(lambda f: fake.goal_result_callback('tb1', 1, f.result()))
    fake.goal_handles['tb1'] = handle
    outcome = CheckpointHeadquarters.allocate_once(fake)
    assert outcome['state'] == 'applied' and fake.allocator.failed['tb1'] == [(2., 1.)]
    assert fake.allocator.robots['tb1'].last_status == 'aborted'
    assert any(e.get('raw_nav2_status') == 5 and e.get('high_level_status') == 'aborted' for e in events)
    results['active_timeout_dispatch'] = dict(events=events, failed=fake.allocator.failed['tb1'])
    # A late accepted pending request is canceled by the unchanged parent method;
    # P7 retains its deadline cause before the immediate cancellation result.
    fake, events = setup(ledger, pending=True)
    fake.allocator.tick(91.)
    future = Future()
    handle = MockHandle('tb1', 2, ledger)
    def deferred_cancel():
        ledger.add('mock_nav2_cancel_requests')
        receipt = Future()
        receipt.set_result(SimpleNamespace(goals_canceling=[handle.goal_id]))
        return receipt
    handle.cancel_goal_async = deferred_cancel
    future.set_result(handle)
    with ledger.call('late_acceptance_callback_fixture'):
        CheckpointHeadquarters.goal_response_callback(fake, 'tb1', 1, future)
    assert fake.allocator.robots['tb1'].state == 'pending' and not fake.allocator.failed['tb1']
    before_terminal = dict(state='pending', failed=[])
    handle.complete(5)
    assert fake.allocator.failed['tb1'] == [(2., 1.)] and fake.allocator.robots['tb1'].last_status == 'aborted'
    results['late_acceptance_timeout'] = dict(before_terminal=before_terminal, events=events, failed=fake.allocator.failed['tb1'])
    ledger.flush('timeout_wiring_end')
    (directory/'result.json').write_text(json.dumps(dict(status='PASS', cases=results,
        real_nn_forward=0, real_env_step=0, node_init=0, optimizer_updates=0,
        ledger_totals=dict(ledger.counts)), indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=Path, required=True)
    args = parser.parse_args()
    run(args.case)
