"""Directed P3/P4 fixes. At most two additional real A steps, no training."""
import argparse
from collections import Counter
from pathlib import Path
import json
import math
import sys
import traceback
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
sys.path.insert(0, str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration.allocation import JointAction, WAIT
from multi_robot_exploration.rl_world import ProjectedWorld
from multi_robot_exploration.rl_backend import KinematicBackend
from multi_robot_exploration.rl_env import RLEnvironment
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.ppo import ActorCritic, load_checkpoint, encode


class OpenROI:
    """Exactly the independent reviewer's already-completed stationary fixture."""
    resolution = .25
    origin = (-5.5, -2.5)
    shape = (30, 50)
    reference_free = np.ones(shape, dtype=bool)
    lidar_obstacles = np.zeros(shape, dtype=bool)

    def cell(self, p):
        return math.floor((p[1]-self.origin[1])/self.resolution), math.floor((p[0]-self.origin[0])/self.resolution)

    def inside(self, p):
        return 0 <= p[0] < self.shape[0] and 0 <= p[1] < self.shape[1]

    def clear(self, p, radius=.25):
        return self.inside(self.cell(p))

    def position(self, cell):
        return np.array([self.origin[0]+(cell[1]+.5)*self.resolution,
                         self.origin[1]+(cell[0]+.5)*self.resolution])


def dump(path, result):
    Path(path).write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')


def main(case, initial):
    case.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(case/'ledger.jsonl', 'gate_supplement')
    config = json.loads((HERE/'config.json').read_text())
    torch.set_num_threads(config['torch_threads'])
    result = dict(status='RUNNING', formal_steps=0)
    try:
        # The OpenROI replay is NOT a training map/episode; all calls still counted.
        ledger.flush('fixture_scope', scope='controlled_open_roi_not_training_A')
        env = RLEnvironment(KinematicBackend(OpenROI(), config['backend'], ledger, 0), None, config, ledger)
        observation, _ = env.reset()
        initial_coverage = env.backend.coverage()
        _, reward, term, trunc, info = env.step(JointAction(observation['decision_id'], observation['map_version'], (WAIT, WAIT, WAIT)))
        assert initial_coverage == 1. and term and not trunc
        assert reward < 0 and info['reward_terms']['first_complete'] == 0
        assert info['reward_terms']['new_free_m2'] == 0 and sum(info['paths_m'].values()) == 0
        result['initial_completion'] = dict(initial_coverage=initial_coverage, reward=reward, terms=info['reward_terms'])
        ledger.flush('fixture_scope', scope='controlled_sensor_occlusion_not_training_A')
        # A complete opaque wall. Cells behind it must remain unobserved.
        world = OpenROI()
        world.lidar_obstacles = np.zeros(world.shape, dtype=bool)
        world.lidar_obstacles[:, 35] = True
        world.reference_free = np.zeros(world.shape, dtype=bool)
        world.reference_free[:, :35] = True
        backend = KinematicBackend(world, config['backend'], ledger, 0)
        backend.reset()
        # tb2 lies strictly left of the wall, so its scan cannot reveal the right.
        assert np.all(backend.local['tb2'][:, 36:] == -1)
        assert np.any(backend.local['tb2'][:, 35] == 100)
        result['occlusion'] = dict(opaque_wall_observed=True, behind_wall_unknown=True)
        assert backend.stop('sensor_fixture_end')
        # Direct transport unit checks: no policy is given actuator/backend access.
        ledger.flush('fixture_scope', scope='controlled_transport_arrival_failure_timeout')
        world = OpenROI()
        backend = KinematicBackend(world, config['backend'], ledger, 0)
        backend.reset()
        at = tuple(backend.poses['tb1'][:2])
        receipt = backend.advance({'tb1': (at, 1)}, .2)
        terminal = [e for e in receipt['events'] if e['kind'] == 'terminal'][0]
        assert terminal['status'] == 'succeeded' and terminal['xy_error_m'] == 0.
        assert terminal['yaw_error_rad'] <= .25
        # Unknown local cell is not silently routed through true free ground.
        target_cell = (10, 20)
        backend.local['tb1'][target_cell] = -1
        target = tuple(world.position(target_cell))
        receipt = backend.advance({'tb1': (target, 2)}, .2)
        assert any(e['kind'] == 'terminal' and e['status'] == 'aborted' for e in receipt['events'])
        # A known path that has already exceeded its navigation budget aborts.
        backend.local['tb1'][:] = 0
        goal = dict(target=np.array([4., 4.]), token=3, started=backend.sim-91,
                    uuid='controlled-timeout', waypoints=[np.array([4., 4.])])
        backend.goals['tb1'] = goal
        receipt = backend.advance({}, .2)
        assert any(e['kind'] == 'terminal' and e['status'] == 'aborted' for e in receipt['events'])
        assert backend.stop('transport_fixture_end')
        result['transport'] = dict(actual_arrival=terminal, unknown_path_aborted=True, timeout_aborted=True,
                                   events=backend.event_log)
        # Both predeclared maps legal, same fixed public ROI and original starts.
        with ledger.call('world_projection_build'):
            world_a = ProjectedWorld(WORKSPACE/'src/multi_robot/worlds/my_world.world',
                                     WORKSPACE.parents[1]/'base-01-econ/assets/gazebo_models', 'A')
            world_b = ProjectedWorld(WORKSPACE/'src/multi_robot/worlds/my_world.world',
                                     WORKSPACE.parents[1]/'base-01-econ/assets/gazebo_models', 'B')
        assert np.allclose(world_a.bounds, config['task_roi']) and np.allclose(world_b.bounds, config['task_roi'])
        assert world_a.shape == world_b.shape and world_a.origin == world_b.origin
        result['fixed_maps'] = dict(roi=config['task_roi'], A_reference_cells=int(world_a.reference_free.sum()),
                                    B_reference_cells=int(world_b.reference_free.sum()),
                                    predeclared_blocks=[[-3., -3., .6], [4., 0., .6]])
        ledger.flush('fixture_scope', scope='real_A_corrected_sensor_pose_two_joint_steps')
        prior = 0
        for path in case.parent.glob('gate-*/ledger.jsonl'):
            prior += sum(json.loads(line)['delta'].get('env_step', 0) for line in path.read_text().splitlines())
        assert prior+2 <= config['gate_joint_steps_max']
        model = ActorCritic(ledger, config['hidden'])
        load_checkpoint(initial, model, restore_rng=True)
        env = RLEnvironment(KinematicBackend(world_a, config['backend'], ledger, config['training_seed']), None, config, ledger)
        observation, _ = env.reset()
        result['corrected_pose_steps'] = []
        for _ in range(2):
            sample = model.act(observation)
            new_obs, reward, term, trunc, info = env.step(sample['action'])
            assert not info['rejected_actions'] and not term and not trunc
            result['corrected_pose_steps'].append(dict(choices=sample['action'].choices, choice_rows=sample['choice_rows'],
                                                       reward=reward, coverage=info['coverage'], sim=env.backend.sim))
            observation = new_obs
        assert result['corrected_pose_steps'][0]['choice_rows'] > 0
        env.allocator.stop('supplement_budget')
        assert env.backend.stop('supplement_budget')
        result['A_genuine_steps_all_gates'] = prior+2
        dump(case/'trajectory.json', env.backend.trajectory)
        dump(case/'navigation-events.json', env.backend.event_log)
        result['status'] = 'DIRECTED FIXES PASS; formal training still pending independent review'
    except Exception as error:
        result.update(status='FAIL', error=f'{type(error).__name__}: {error}', traceback=traceback.format_exc())
        raise
    finally:
        ledger.flush('supplement_end')
        result['ledger_totals'] = dict(ledger.counts)
        dump(case/'result.json', result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--initial', type=Path, required=True)
    args = parser.parse_args()
    main(args.case, args.initial)
