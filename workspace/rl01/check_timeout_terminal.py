"""Directed callback fixture: zero NN forwards, Node init, env or optimizer use."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import threading
from multi_robot_exploration.allocation import Allocator
from multi_robot_exploration.control import HeadquartersControl
from multi_robot_exploration.rl_ledger import Ledger
from ros_policy import CheckpointHeadquarters


def run(directory, fixed):
    directory.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(directory/'ledger.jsonl', 'directed_timeout_terminal_fixture')
    results = {}
    for name, marker, now, current_token, raw in (
            ('own_timeout_cancel', True, 91., 1, 5),
            ('external_cancel', False, 20., 1, 5),
            ('external_cancel_late_receipt', False, 91., 1, 5),
            ('stale_timeout_token', True, 91., 2, 5),
            ('normal_success', False, 20., 1, 4),
            ('normal_abort', False, 20., 1, 6),
            ('timeout_success_race', True, 91., 1, 4)):
        events = []
        allocator = Allocator(emit=events.append, task_timeout_s=90.)
        robot = allocator.robots['tb1']
        robot.state, robot.target, robot.token, robot.started, robot.uuid = 'active', (1., 1.), current_token, 0., 'controlled-uuid'
        if current_token == 2:
            robot.started = 85.
        # map_callback can tick before an external cancellation receipt, without
        # P7 ever dispatching its own timeout cancellation. Existing flag alone
        # is therefore insufficient to identify the cause of raw CANCELED.
        if (marker and current_token == 1) or name == 'external_cancel_late_receipt':
            allocator.tick(91.)
        flag_before = robot.cancel_requested
        fake = SimpleNamespace(lock=threading.RLock(), allocator=allocator, goal_handles={'tb1': object()},
            timeout_cancel_tokens={('tb1', 1)} if marker else set(),
            now=lambda now=now: now, record=events.append,
            get_logger=lambda: SimpleNamespace(info=lambda message: None))
        with ledger.call('typed_terminal_callback_fixture', fixture=name):
            message = SimpleNamespace(status=raw)
            CheckpointHeadquarters.goal_result_callback(fake, 'tb1', 1, message)
            assert message.status == raw
        results[name] = dict(last_status=robot.last_status, state=robot.state, token=robot.token,
                             raw_nav2_status=raw, timeout_flag_before_terminal=flag_before,
                             own_timeout_dispatch_recorded=marker,
                             failed_targets=list(allocator.failed['tb1']), events=events,
                             goal_handle_retained='tb1' in fake.goal_handles)
    consistent = results['own_timeout_cancel']['last_status'] == 'aborted' and results['own_timeout_cancel']['failed_targets'] == [(1., 1.)]
    assert results['external_cancel']['last_status'] == 'canceled' and not results['external_cancel']['failed_targets']
    assert results['external_cancel_late_receipt']['last_status'] == 'canceled' and not results['external_cancel_late_receipt']['failed_targets']
    assert results['stale_timeout_token']['state'] == 'active' and results['stale_timeout_token']['goal_handle_retained']
    assert results['normal_success']['last_status'] == 'succeeded'
    assert results['normal_abort']['last_status'] == 'aborted' and results['normal_abort']['failed_targets']
    assert results['timeout_success_race']['last_status'] == 'succeeded' and not results['timeout_success_race']['failed_targets']
    assert consistent if fixed else not consistent
    ledger.flush('timeout_fixture_end')
    (directory/'result.json').write_text(json.dumps(dict(status='FIX PASS' if fixed else 'MISMATCH REPRODUCED',
        timeout_failed_exclusion_consistent=consistent, cases=results, real_nn_forward=0,
        node_init=0, real_env_step=0, optimizer_updates=0, ledger_totals=dict(ledger.counts)), indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--expect-fixed', action='store_true')
    args = parser.parse_args()
    run(args.case, args.expect_fixed)
