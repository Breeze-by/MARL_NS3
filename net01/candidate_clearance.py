"""Opt-in candidate geometry matching the declared circular Nav2 footprint.

For occupancy cell width r and robot radius R, inflate occupied cell centres
by R + r/sqrt(2). Thus a remaining free grid centre is farther than R from
every point in each occupied square cell. This is a guarantee at grid centres,
not a continuous-path or dynamic-obstacle guarantee; original Nav2 checks stay.
Unknown/nonzero source cells never become free. Peer/goal/history gates stay.
"""
from contextlib import contextmanager
import json
import math
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_dilation

VERSION = 'nav2-circular-footprint-v1'


def circular_costmap(data, width, height, resolution, robot_radius):
    cells = np.array(data, copy=True).reshape(height, width)
    clearance = robot_radius + resolution / math.sqrt(2)
    reach = math.ceil(clearance / resolution)
    rows, columns = np.ogrid[-reach:reach + 1, -reach:reach + 1]
    footprint = (rows * resolution)**2 + (columns * resolution)**2 <= clearance**2
    cells[binary_dilation(cells == 100, structure=footprint)] = 100
    return cells * resolution


@contextmanager
def candidate_costmap_scope(robot_radius):
    from multi_robot_exploration import frontier
    original = frontier.costmap
    frontier.costmap = lambda data, width, height, resolution: circular_costmap(
        data, width, height, resolution, robot_radius)
    try:
        yield
    finally:
        frontier.costmap = original


def install_candidate_clearance(node, contract):
    if contract['id'] != VERSION:
        raise ValueError('Unknown explicit candidate clearance contract')
    radii = contract['nav2_robot_radius_m']
    if radii != {'tb1': .25, 'tb2': .25, 'tb3': .25} or contract['map_resolution_m'] != .05:
        raise ValueError('This version binds the actual three .25m circular radii and .05m candidate grid')
    radius = radii['tb1']
    original = node.allocator.get_observation
    state = dict(contract=contract, calls=0,
        derived_occupied_centre_clearance_m=radius + contract['map_resolution_m']/math.sqrt(2),
        formula='occupied-centre inflation radius = nav2_robot_radius_m + map_resolution_m/sqrt(2)',
        scope='New candidate behavior baseline; same original allocator, input grids, policy weights and 701 structure; no continuous-path guarantee')
    def observation(*args, **kwargs):
        if node.allocator.map['resolution'] != contract['map_resolution_m']:
            raise ValueError('Candidate map resolution differs from the explicit repair contract')
        state['calls'] += 1
        with candidate_costmap_scope(radius):
            return original(*args, **kwargs)
    node.allocator.get_observation = observation
    node._candidate_clearance_state = state


def candidate_headquarters(original, profile):
    from nav2_goal_guard import install_goal_guard
    class CandidateHeadquarters(original):
        def __init__(self, checkpoint, expected_sha256, directory, *args, **kwargs):
            super().__init__(checkpoint, expected_sha256, directory, *args, **kwargs)
            install_candidate_clearance(self, profile['candidate_clearance'])
            install_goal_guard(self, profile)
            self._candidate_clearance_directory = Path(directory)

        def record(self, event):
            result = super().record(event)
            if event['kind'] == 'rl_actual_nav2_goal_request':
                self._nav2_goal_guard.observe_request(event)
            return result

        def destroy_node(self):
            try:
                self._nav2_goal_guard.finish()
                with (self._candidate_clearance_directory / 'candidate-clearance.json').open('x') as stream:
                    json.dump(self._candidate_clearance_state, stream, indent=2, allow_nan=False)
                    stream.write('\n')
            finally:
                result = super().destroy_node()
            return result
    return CandidateHeadquarters
