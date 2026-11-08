"""One sequential reservation rule for sampling, likelihood and allocator WAIT."""
import math
import numpy as np
from .allocation import JointAction, TraditionalPolicy, KEEP, WAIT, idle_body_goal_valid

MAX_CANDIDATES = 15
KEEP_SLOT, WAIT_SLOT = 15, 16


def candidate_mask(observation, row, prefix=()):
    separation=observation.get('goal_separation_m',.2)
    mask = list(observation['action_mask'][row])
    reserved = []
    conflicts={tuple(pair) for pair in observation.get('candidate_conflicts',())}
    reserved_indices=[]
    for earlier, choice in enumerate(prefix[:row]):
        if 0 <= choice < len(observation['candidates']):
            prior = observation['candidates'][choice]['position']
            # Invalid earlier choices do not acquire ownership.
            if (observation['action_mask'][earlier][choice] and idle_body_goal_valid(
                    observation,observation['robots'][earlier]['id'],prior)) and not any(
                    math.dist(prior, target) < separation for target in reserved) and not any(
                    tuple(sorted((choice,index))) in conflicts for index in reserved_indices):
                reserved.append(prior);reserved_indices.append(choice)
    return tuple(legal and idle_body_goal_valid(observation,observation['robots'][row]['id'],c['position'])
                 and not any(math.dist(c['position'], target) < separation
                                  for target in reserved)
                 and not any(tuple(sorted((index,prior))) in conflicts for prior in reserved_indices)
                 for index,(legal,c) in enumerate(zip(mask, observation['candidates'])))


def _base_slot_mask(observation, row, prefix=()):
    if observation.get('halted'):
        raise ValueError('No policy action after allocator halt')
    if len(observation['candidates']) > MAX_CANDIDATES:
        raise ValueError('BASE02 candidate bound exceeded')
    mask = np.zeros(17, dtype=bool)
    robot = observation['robots'][row]
    if robot['state'] != 'idle':
        mask[KEEP_SLOT] = True
    elif observation.get('trigger') is not None and observation['trigger'] != robot['id']:
        mask[WAIT_SLOT] = True
    else:
        legal = candidate_mask(observation, row, prefix)
        mask[:len(legal)] = legal
        mask[WAIT_SLOT] = not any(legal)
    return mask


def _suffix_work(observation, row, prefix):
    if row == len(observation['robots']):
        return 0
    return max(int(slot < MAX_CANDIDATES) + _suffix_work(
        observation,row+1,(*prefix,slot_to_choice(slot)))
        for slot in np.flatnonzero(_base_slot_mask(observation,row,prefix)))


def slot_mask(observation, row, prefix=()):
    mask=_base_slot_mask(observation,row,prefix)
    if observation.get('joint_assignment_rule') != 'maximum-participation-v1' or mask.sum()<=1:
        return mask
    scores={slot:int(slot < MAX_CANDIDATES) + _suffix_work(
        observation,row+1,(*prefix,slot_to_choice(slot))) for slot in np.flatnonzero(mask)}
    best=max(scores.values())
    for slot,score in scores.items():mask[slot]=score==best
    return mask


def choice_to_slot(choice):
    return KEEP_SLOT if choice == KEEP else WAIT_SLOT if choice == WAIT else choice


def slot_to_choice(slot):
    return KEEP if slot == KEEP_SLOT else WAIT if slot == WAIT_SLOT else int(slot)


class JointTraditionalPolicy:
    """Original per-robot selector, with sequential legally acquired reservations.

    No change to its ranking, local-invalid failure or last-success veto. The
    standard ROS single-trigger TraditionalPolicy is left untouched.
    """
    def select(self, observation):
        choices = []
        separation=observation.get('goal_separation_m',.2)
        original = TraditionalPolicy()
        for row, robot in enumerate(observation['robots']):
            joint_legal=(slot_mask(observation,row,choices) if
                observation.get('joint_assignment_rule')=='maximum-participation-v1' else None)
            view = dict(observation)
            view['trigger'] = robot['id']
            candidates = [dict(c) for c in observation['candidates']]
            # Only remove additional reservations; preserve original eligibility
            # even for a locally-invalid or last-success-vetoed best candidate.
            reserved = [observation['candidates'][p]['position'] for j, p in enumerate(choices)
                        if p >= 0 and observation['action_mask'][j][p]]
            for candidate in candidates:
                if ((joint_legal is not None and not joint_legal[candidate['index']]) or
                        not idle_body_goal_valid(observation,robot['id'],candidate['position']) or
                        any(math.dist(candidate['position'], p) < separation for p in reserved)):
                    candidate['traditional_eligible'] = False
            view['candidates'] = candidates
            choice = original.select(view).choices[row]
            choices.append(choice)
        return JointAction(observation['decision_id'], observation['map_version'], tuple(choices))
