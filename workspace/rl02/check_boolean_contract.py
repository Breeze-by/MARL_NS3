"""Zero-step proof of proxy/ROS bool mismatch in failed-goal exclusion."""
import json
from types import SimpleNamespace
import numpy as np
from nav_msgs.msg import OccupancyGrid
from maps import PROJECT, dump
from multi_robot_exploration.allocation import Allocator, JointAction, WAIT, frozen
from multi_robot_exploration.rl_backend import KinematicBackend
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.control import HeadquartersControl


def apply_flag(flag):
    allocator = Allocator()
    allocator.decision_id = allocator.map_version = 1
    observation = frozen(dict(decision_id=1, map_version=1, trigger='tb1',
        robots=[dict(task_token=0, state='idle') for _ in range(3)],
        candidates=[dict(robot='tb1', position=(.5, .5), traditional_eligible=True,
                         local_map_valid=flag, valid=False)],
        action_mask=[[False], [False], [False]]))
    proposals, rejected = allocator.apply(observation, JointAction(1, 1, (0, WAIT, WAIT)))
    return dict(input_type=type(flag).__name__, retained_type=type(observation['candidates'][0]['local_map_valid']).__name__,
        rejected=rejected, failed_targets=allocator.failed['tb1'], proposals=proposals)


def run():
    output = PROJECT/'evidence/boolean-contract-01'
    output.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(output/'ledger.jsonl', 'static_boolean_contract')
    backend = object.__new__(KinematicBackend)
    backend.world = SimpleNamespace(cell=lambda position: (0, 0), inside=lambda cell: True)
    backend.local = {'tb1': np.array([[-1]], dtype=np.int16)}
    backend.ledger = ledger
    proxy = backend.goal_valid('tb1', .5, .5)
    grid = OccupancyGrid()
    grid.info.height = grid.info.width = 1
    grid.info.resolution = 1.
    grid.info.origin.orientation.w = 1.
    grid.data = [-1]
    node = SimpleNamespace(local_maps={'tb1': grid})
    ros = HeadquartersControl.nav_goal_in_local_map(node, 'tb1', .5, .5)
    proxy_result, ros_result = apply_flag(proxy), apply_flag(ros)
    mismatch = (isinstance(proxy, np.bool_) and type(ros) is bool and not proxy and not ros
        and proxy_result['failed_targets'] == [] and ros_result['failed_targets'] == [(.5, .5)])
    ledger.flush('boolean_contract_proof')
    result = dict(status='CONTRACT MISMATCH CONFIRMED' if mismatch else 'MISMATCH NOT REPRODUCED',
        proxy=proxy_result, actual_typed_ROS_local_check=ros_result,
        consequence='Proxy invalid local candidate is rejected but is not inserted into failed-target history, unlike the actual ROS check; original-selector comparison is potentially unfair.',
        actual_backend_init=0, actual_ros_node_init=0, allocator_apply_fixture_calls=2,
        nn_forward=0, env_reset=0, env_step=0, optimizer_step=0, gazebo_start=0,
        actual_production_sources_modified=False, counts=dict(ledger.counts))
    dump(output/'result.json', result)
    print(json.dumps(result, indent=2))
    if not mismatch:
        raise AssertionError('Investigated Boolean mismatch was not reproduced')


if __name__ == '__main__':
    run()
