"""Scalar task reward layered over the actual BASE02 state/action lifecycle."""
import math
import numpy as np
from .environment import AllocationEnvironment


def reward_value(terms, weights):
    value = sum(terms[name]*weight for name, weight in weights.items())
    if not math.isfinite(value):
        raise ValueError('Nonfinite task reward')
    return float(value)


class RLEnvironment(AllocationEnvironment):
    def __init__(self, backend, policy, config, ledger):
        super().__init__(backend, policy, config['episode_decisions'], config['step_sim_seconds'], config['task_roi'],
            config.get('candidate_mode','legacy'), config.get('navigation_path_budget_m'),config['backend']['xy_goal_tolerance_m'])
        self.config, self.ledger = config, ledger

    def _snapshot(self, snapshot):
        self.ledger.add('allocator_observation_build')
        super()._snapshot(snapshot)

    def reset(self):
        with self.ledger.call('env_reset'):
            observation, info = super().reset()
            self.reward_total = 0.
            self.completion_paid = self.backend.coverage() >= .95
            self.steps = []
            self.initial_coverage = self.backend.coverage()
            return observation, info

    def get_observation(self):
        with self.ledger.call('env_get_observation'):
            return super().get_observation()

    def get_action_mask(self):
        with self.ledger.call('env_get_action_mask'):
            return super().get_action_mask()

    def step(self, action=None):
        with self.ledger.call('env_step'):
            b = self.backend
            before_free, before_known = b.shared == 0, b.shared >= 0
            before_local = {r: m >= 0 for r, m in b.local.items()}
            before_sim, before_path = b.sim, sum(b.paths.values())
            trace_index = len(b.trajectory)
            observation, vector, terminated, truncated, info = super().step(action)
            elapsed, distance = b.sim-before_sim, sum(b.paths.values())-before_path
            new_known = int(np.count_nonzero((b.shared >= 0) & ~before_known))
            new_free = int(np.count_nonzero((b.shared == 0) & ~before_free))
            local_new = sum(np.count_nonzero((b.local[r] >= 0) & ~before_local[r]) for r in b.local)
            rotation = sum(abs(v['velocities'][r][2]) for v in b.trajectory[trace_index:] for r in b.local)
            stationary = distance < 1e-9 and rotation < 1e-9 and new_known == 0
            terms = dict(new_free_m2=new_free*b.world.resolution**2,
                         sim_seconds=elapsed, path_m=distance,
                         duplicate_new_m2=max(0, int(local_new)-new_known)*b.world.resolution**2,
                         stationary_no_progress_seconds=elapsed if stationary else 0.,
                         first_complete=float(terminated and not self.completion_paid))
            self.completion_paid |= terminated
            reward = reward_value(terms, self.config['reward'])
            self.reward_total += reward
            info.update(reward_terms=terms, base02_reward_vector=vector, coverage=b.coverage(),
                        coverage_times=dict(b.coverage_times), paths_m=dict(b.paths),
                        minimum_pair_m=b.minimum_pair, safe_blocks=b.safe_blocks,
                        reward_total=self.reward_total, bootstrap_valid=info['reason'] in
                        (None, 'decision_budget', 'stalled_wait', 'natural_complete'))
            self.steps.append(dict(decision=self.decisions, sim=b.sim, reward=reward, terms=terms,
                                   terminated=terminated, truncated=truncated, reason=info['reason'],
                                   coverage=info['coverage'], choices=None if action is None else action.choices,
                                   rejections=info['rejected_actions']))
            return observation, reward, terminated, truncated, info
