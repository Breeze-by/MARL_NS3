"""Static post-TEST callback-contract repair; no model or environment run."""
import ast
import json
from types import SimpleNamespace

import numpy as np
from nav_msgs.msg import OccupancyGrid
from maps import PROJECT, dump
from check_boolean_contract import apply_flag
from multi_robot_exploration.allocation import Allocator, JointAction, frozen
from multi_robot_exploration.control import HeadquartersControl
from multi_robot_exploration.joint import slot_mask
from multi_robot_exploration.observations import TASK_ROI
from multi_robot_exploration.ppo import encode
from multi_robot_exploration.rl_backend import KinematicBackend
from multi_robot_exploration.rl_ledger import Ledger

FORMAL_SOURCE = '4cdbc870585e2a75825f2fd498ba0eb3c2a7508e'


def observation(flags):
    robots = [dict(id=name, pose=(i+1., 1., 0.), velocity=(0., 0., 0.),
                   state='idle', target=None, task_token=0, goal_duration_s=None)
              for i, name in enumerate(('tb1', 'tb2', 'tb3'))]
    candidates = []
    for i, robot in enumerate(robots):
        for j, flag in enumerate(flags):
            candidates.append(dict(robot=robot['id'], position=(3.*i+j+.5, .5),
                traditional_eligible=True, local_map_valid=flag, valid=bool(flag),
                reachable=True, path_cost_estimate_m=1., information_gain_proxy_m2=.5))
    masks = [[c['robot']==r['id'] and c['valid'] for c in candidates] for r in robots]
    return frozen(dict(decision_id=1, map_version=1, trigger=None, robots=robots,
        candidates=candidates, action_mask=masks, halted=None,
        map=dict(cells=np.zeros((16, 16), dtype=np.int16), resolution=.05,
                 origin=tuple(TASK_ROI[:2]))))


def run():
    output = PROJECT/'evidence/boolean-fix-02'
    output.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(output/'ledger.jsonl', 'static_boolean_fix')
    old_source = (PROJECT/'evidence/boolean-fix-input-01/rl_backend.py').read_text()
    old_class = next(n for n in ast.parse(old_source).body
                     if isinstance(n, ast.ClassDef) and n.name=='KinematicBackend')
    old_method = next(n for n in old_class.body
                      if isinstance(n, ast.FunctionDef) and n.name=='goal_valid')
    namespace = {}
    exec(compile(ast.Module(body=[old_method], type_ignores=[]),
                 '<pinned-formal-goal-valid>', 'exec'), namespace)
    legacy = namespace['goal_valid']
    backend = object.__new__(KinematicBackend)
    backend.world = SimpleNamespace(cell=lambda p: (0, int(p[0])),
                                    inside=lambda c: 0<=c[1]<3)
    backend.local = {'tb1': np.array([[-1, 0, 100]], dtype=np.int16)}
    backend.ledger = ledger
    cases, flags = {}, {}
    for label, x in [('unknown', .5), ('free', 1.5), ('occupied', 2.5), ('outside', 3.5)]:
        old, new = legacy(backend, 'tb1', x, .5), backend.goal_valid('tb1', x, .5)
        assert bool(old)==new and type(new) is bool
        flags[label] = (old, new)
        cases[label] = dict(old_type=type(old).__name__, new_type=type(new).__name__, value=new)
    old_obs = observation([flags['unknown'][0], flags['free'][0]])
    new_obs = observation([flags['unknown'][1], flags['free'][1]])
    assert old_obs['action_mask']==new_obs['action_mask']
    assert np.array_equal(encode(old_obs), encode(new_obs))
    # All controlled candidate/KEEP/WAIT prefixes, including rejected prefixes.
    prefixes = [()]
    mask_pairs = 0
    for row in range(3):
        for prefix in prefixes:
            assert np.array_equal(slot_mask(old_obs, row, prefix), slot_mask(new_obs, row, prefix))
            mask_pairs += 1
        prefixes = [p+(choice,) for p in prefixes for choice in (-2, -1, *range(6))]
    legal = []
    for obs in (old_obs, new_obs):
        allocator = Allocator()
        allocator.decision_id = allocator.map_version = 1
        proposals, rejected = allocator.apply(obs, JointAction(1, 1, (1, 3, 5)))
        assert not rejected and len(proposals)==3 and not any(allocator.failed.values())
        legal.append((proposals, rejected, allocator.failed))
    assert legal[0]==legal[1]
    old_invalid, new_invalid = [apply_flag(flag) for flag in flags['unknown']]
    assert old_invalid['failed_targets']==[]
    assert new_invalid['failed_targets']==[(.5, .5)]
    assert old_invalid['rejected']==new_invalid['rejected']
    grid = OccupancyGrid()
    grid.info.height = 1
    grid.info.width = 3
    grid.info.resolution = 1.
    grid.info.origin.orientation.w = 1.
    grid.data = [-1, 0, 100]
    node = SimpleNamespace(local_maps={'tb1': grid})
    for label, x in [('unknown', .5), ('free', 1.5), ('occupied', 2.5), ('outside', 3.5)]:
        actual = HeadquartersControl.nav_goal_in_local_map(node, 'tb1', x, .5)
        assert type(actual) is bool and actual==flags[label][1]
    node.local_maps = {}
    node.local_point = lambda robot, target: (SimpleNamespace(x=target[0], y=target[1]), None)
    assert HeadquartersControl.goal_valid(node, 'tb1', .5, .5) is None
    ledger.flush('boolean_fix_complete')
    result = dict(status='PASS', historical_source_commit=FORMAL_SOURCE,
        callback_cases=cases, encoded_features=701, encode_bitwise_equal=True,
        action_masks_equal=True, conditional_mask_prefix_pairs=mask_pairs,
        legal_three_goal_apply_equal=True, old_invalid=old_invalid, fixed_invalid=new_invalid,
        actual_typed_ROS_bool_matches=True, ROS_missing_map_None_preserved=True,
        actual_backend_init=0, actual_ros_node_init=0, env_reset=0, env_step=0,
        nn_forward=0, optimizer_step=0, gazebo_start=0,
        allocator_apply_fixture_calls=4, counts=dict(ledger.counts),
        scope='Controlled contract fixture, not a replacement evaluation or rollout; no counterfactual performance claim.')
    dump(output/'result.json', result)
    print(json.dumps(result, indent=2))


if __name__=='__main__':
    run()
