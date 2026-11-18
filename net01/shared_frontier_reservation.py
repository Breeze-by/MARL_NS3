"""Explicit received shared-frontier cell ownership over the original allocator."""
import json
import math
import os
from pathlib import Path
import time

VERSION = 'shared-frontier-cell-reservation-v1'
CONTRACT_FILE = 'config/NAVIGATION_SHARED_FRONTIER_RESERVATION_V1.json'


def load_contract(revision):
    contract = json.loads((Path(__file__).resolve().parent/CONTRACT_FILE).read_text())
    if revision != VERSION or contract['revision'] != VERSION or contract['cell_resolution_m'] != .05:
        raise ValueError('Unknown shared frontier cell reservation revision')
    return contract


class SharedFrontierReservation:
    def __init__(self, node, contract):
        self.node = node
        self.contract = dict(contract)
        if node.allocator.candidate_mode != 'rl04_approach_v2':
            raise ValueError('Shared frontier reservations require original approach-v2 metadata')
        self.directory = Path(node.events.name).parent
        self.reservations = {}
        self.events = []
        self.finished = False

    def record(self, kind, **fields):
        self.events.append(dict(kind=kind, monotonic_ns=time.monotonic_ns(), **fields))

    @staticmethod
    def cell(position, observation):
        grid = observation['map']
        if grid['resolution'] != .05:
            raise ValueError('This revision requires the original .05m shared lattice')
        return tuple(math.floor((position[i]-grid['origin'][i])/grid['resolution']) for i in (0, 1))

    def observe(self, observation):
        from multi_robot_exploration.allocation import frozen
        candidates = observation['candidates']
        if not candidates:
            return observation
        cells = [self.cell(c['shared_frontier_position'], observation) for c in candidates]
        reserved = {robot:self.cell(r['shared_frontier_position'], observation)
                    for robot, r in self.reservations.items()}
        masks, blocked = [], []
        for row, robot in enumerate(observation['robots']):
            mask = []
            for index, legal in enumerate(observation['action_mask'][row]):
                conflict = legal and any(owner != robot['id'] and cell == cells[index]
                                         for owner, cell in reserved.items())
                mask.append(bool(legal and not conflict))
                if conflict:
                    blocked.append(dict(robot=robot['id'], candidate=index, cell=cells[index]))
            masks.append(tuple(mask))
        added = {(i, j) for i, c in enumerate(candidates) for j in range(i+1, len(candidates))
                 if c['robot'] != candidates[j]['robot'] and cells[i] == cells[j]}
        conflicts = set(map(tuple, observation['candidate_conflicts'])) | added
        self.record('intent_mask', decision_id=observation['decision_id'],
                    map_version=observation['map_version'], blocked_by_owned_intents=blocked,
                    same_snapshot_intent_pairs=sorted(added), owned=list(self.reservations.values()))
        return frozen(dict(observation, action_mask=tuple(masks),
                           valid_counts=tuple(sum(mask) for mask in masks),
                           wait_mask=tuple(r['state'] == 'idle' and not observation['halted']
                                           and not any(mask)
                                           for r, mask in zip(observation['robots'], masks)),
                           candidate_conflicts=tuple(sorted(conflicts))))

    def apply(self, original, observation, action):
        proposals, rejected = original(observation, action)
        rows = list(self.node.allocator.robots)
        for robot, (target, token) in proposals.items():
            candidate = observation['candidates'][action.choices[rows.index(robot)]]
            reservation = dict(robot=robot, token=token, target=tuple(target),
                               shared_frontier_position=tuple(candidate['shared_frontier_position']),
                               source_decision_id=observation['decision_id'],
                               source_map_version=observation['map_version'])
            self.reservations[robot] = reservation
            self.record('intent_reserved_after_original_pending_proposal', **reservation)
        return proposals, rejected

    def finish(self, original, robot, token, status):
        uuid_before = self.node.allocator.robots[robot].uuid
        completed = original(robot, token, status)
        reservation = self.reservations.get(robot)
        if completed and reservation is not None and reservation['token'] == token:
            self.reservations.pop(robot)
            self.record('intent_released_after_original_finish_true', status=status,
                        uuid_before=uuid_before, **reservation)
        return completed

    def finish_recording(self):
        if self.finished:
            return
        self.finished = True
        with (self.directory/'shared-frontier-reservations.json').open('x') as stream:
            json.dump(dict(revision=VERSION, contract=self.contract, PID=os.getpid(), events=self.events,
                           still_owned=list(self.reservations.values()),
                           scope='Actual received candidate metadata and original pending/finishTrue tasks; no groupID/TTL/truth/newGoal or syntheticterminal.'), stream, indent=2)


def install_shared_frontier_reservation(node, contract):
    helper = SharedFrontierReservation(node, contract)
    original_observe = node.allocator.get_observation
    original_apply = node.allocator.apply
    original_finish = node.allocator.finish

    def observe(*args, **kwargs):
        with node.lock:
            return helper.observe(original_observe(*args, **kwargs))

    def apply(observation, action):
        with node.lock:
            return helper.apply(original_apply, observation, action)

    def finish(robot, token, status):
        with node.lock:
            return helper.finish(original_finish, robot, token, status)

    node.allocator.get_observation = observe
    node.allocator.apply = apply
    node.allocator.finish = finish
    node._shared_frontier_reservation = helper
    return helper
