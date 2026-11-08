"""Bounded kinematic proxy for the BASE02 backend; explicitly not Nav2/Gazebo."""
import heapq
import math
import numpy as np
from scipy.ndimage import maximum_filter

ROBOTS = ('tb1', 'tb2', 'tb3')


def angle(value):
    return (value+math.pi) % (2*math.pi)-math.pi


def swept_pair_distance(a0, a1, b0, b1):
    """Exact minimum distance during simultaneous straight physical substeps."""
    relative = np.asarray(a0)-b0
    delta = (np.asarray(a1)-a0)-(np.asarray(b1)-b0)
    denominator = float(delta @ delta)
    time = 0. if denominator == 0 else float(np.clip(-(relative @ delta)/denominator, 0., 1.))
    return float(np.linalg.norm(relative+time*delta))


def route(cells, start, goal, resolution):
    """A* in observed free cells, original seven-cell obstacle inflation."""
    wall = maximum_filter(cells == 100, size=15, mode='nearest')
    free = (cells == 0) & ~wall
    free[start] = True  # Same observed current-cell exception as BASE02.
    if not free[goal]:
        return None
    queue = [(0., 0., start)]
    costs, parent = {start: 0.}, {}
    while queue:
        _, cost, cell = heapq.heappop(queue)
        if cost != costs[cell]:
            continue
        if cell == goal:
            path = [cell]
            while path[-1] != start:
                path.append(parent[path[-1]])
            return list(reversed(path))
        r, c = cell
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            rr, cc = r+dr, c+dc
            if not (0 <= rr < free.shape[0] and 0 <= cc < free.shape[1]) or not free[rr, cc]:
                continue
            if dr and dc and not (free[r, cc] and free[rr, c]):
                continue
            value = cost+math.hypot(dr, dc)*resolution
            if value < costs.get((rr, cc), math.inf):
                costs[(rr, cc)] = value
                parent[(rr, cc)] = cell
                heuristic = math.hypot(rr-goal[0], cc-goal[1])*resolution
                heapq.heappush(queue, (value+heuristic, value, (rr, cc)))
    return None


class KinematicBackend:
    def __init__(self, world, config, ledger, seed):
        self.world, self.config, self.ledger, self.seed = world, config, ledger, seed
        self.episode = 0
        self.dt = config['physics_dt']
        self.rays = config['lidar_rays']
        self.ranges = np.arange(0, config['lidar_range_m']+world.resolution/4, world.resolution/2)

    def reset(self):
        with self.ledger.call('backend_reset', seed=self.seed):
            self.episode += 1
            self.sim = 0.
            self.poses = {r: np.array([*p, 0.], dtype=float)
                          for r, p in zip(ROBOTS, self.config['initial_positions'])}
            self.velocity = {r: np.zeros(3) for r in ROBOTS}
            self.local = {r: np.full(self.world.shape, -1, dtype=np.int16) for r in ROBOTS}
            self.goals, self.events, self.cache = {}, [], {}
            self.event_log = []
            self.paths = {r: 0. for r in ROBOTS}
            self.trajectory = []
            self.safe_blocks = 0
            self.minimum_pair = math.inf
            self.done_completion = False
            self.coverage_times = {}
            rng = np.random.default_rng(self.seed)
            self.offsets = dict(zip(ROBOTS, rng.uniform(0, 2*math.pi/self.rays, 3)))
            if not all(self.world.clear(p) for p in self.poses.values()):
                raise ValueError('Unsafe initial source pose')
            self._scan_all()
            self.previous_free = self.shared == 0
            self.previous_known = self.shared >= 0
            self.previous_local = {r: self.local[r] >= 0 for r in ROBOTS}
            self._record()
            return dict(episode_id=f'{self.seed}-{self.episode}', world_reset=True,
                        slam_reset=True, navigation_cleared=True, snapshot=self.snapshot())

    def _scan_all(self):
        for robot in ROBOTS:
            self.ledger.add('sensor_scans_scheduled')
            pose = self.poses[robot]
            key = tuple(np.round(pose, 9))
            if self.cache.get(robot) == key:
                self.ledger.add('sensor_stationary_cache_hits')
                continue
            self.cache[robot] = key
            self.ledger.add('sensor_raycast_computations')
            angles = pose[2]+self.offsets[robot]+np.arange(self.rays)*2*math.pi/self.rays
            # Source ray sensor pose (not its inertial pose), plus declared .01m spawn z.
            origin = pose[:2]+self.config['lidar_x_offset_m']*np.array([math.cos(pose[2]), math.sin(pose[2])])
            xs = origin[0]+np.cos(angles)[:, None]*self.ranges
            ys = origin[1]+np.sin(angles)[:, None]*self.ranges
            cols = np.floor((xs-self.world.origin[0])/self.world.resolution).astype(int)
            rows = np.floor((ys-self.world.origin[1])/self.world.resolution).astype(int)
            inside = (rows >= 0) & (rows < self.world.shape[0]) & (cols >= 0) & (cols < self.world.shape[1])
            rr, cc = rows.clip(0, self.world.shape[0]-1), cols.clip(0, self.world.shape[1]-1)
            hits = inside & self.world.lidar_obstacles[rr, cc]
            # Leaving the finite task ROI ends a ray without inventing a wall.
            stop = hits | ~inside
            visible = inside & (np.cumsum(stop, axis=1)-stop == 0)
            self.local[robot][rr[visible], cc[visible]] = 0
            ends = visible & hits
            self.local[robot][rr[ends], cc[ends]] = 100
        self.shared = np.maximum.reduce(list(self.local.values()))

    def goal_valid(self, robot, x, y):
        self.ledger.add('backend_goal_valid')
        cell = self.world.cell((x, y))
        # No true occupancy, clearance, reference mask or future sensing here.
        return bool(self.world.inside(cell) and self.local[robot][cell] == 0)

    def navigation_grid(self, robot, shared):
        # Sensor-delivered local cells already use the fixed shared ROI grid.
        # Do not access world geometry or simulator state for candidate routing.
        return self.local[robot]

    def _terminal(self, robot, status):
        goal = self.goals.pop(robot)
        event = dict(kind='terminal', robot=robot, token=goal['token'],
                     status=status, sim=self.sim, uuid=goal['uuid'], target=goal['target'].tolist(),
                     actual_pose=self.poses[robot].tolist(),
                     xy_error_m=float(np.linalg.norm(self.poses[robot][:2]-goal['target'])),
                     yaw_error_rad=abs(angle(-self.poses[robot][2])))
        self.events.append(event)
        self.event_log.append(dict(event))
        self.velocity[robot][:] = 0

    def advance(self, proposals, max_sim_s):
        with self.ledger.call('backend_advance', requested_sim_s=max_sim_s):
            self.events = []
            for robot, (target, token) in proposals.items():
                if robot in self.goals:
                    raise ValueError('Active task cannot be replaced')
                goal = dict(target=np.array(target), token=token, started=self.sim,
                            uuid=f'{self.seed}:{self.episode}:{robot}:{token}')
                self.goals[robot] = goal
                event = dict(kind='accepted', robot=robot, token=token, uuid=goal['uuid'],
                             sim=self.sim, target=list(target), actual_pose=self.poses[robot].tolist())
                self.events.append(event)
                self.event_log.append(dict(event))
                self.ledger.add('navigation_plans')
                path = route(self.local[robot], self.world.cell(self.poses[robot]),
                             self.world.cell(target), self.world.resolution)
                if path is None:
                    self._terminal(robot, 'aborted')
                else:
                    goal['waypoints'] = [self.world.position(p) for p in path[1:]]
            start = self.sim
            while self.sim-start < max_sim_s-1e-8:
                dt = min(self.dt, max_sim_s-(self.sim-start))
                old = {r: p.copy() for r, p in self.poses.items()}
                self.ledger.add('physics_ticks')
                for robot in ROBOTS:
                    self.velocity[robot][:] = 0
                    if robot not in self.goals:
                        continue
                    goal = self.goals[robot]
                    pose = self.poses[robot]
                    target_error = np.linalg.norm(pose[:2]-goal['target'])
                    if target_error <= self.config['xy_goal_tolerance_m']:
                        error = angle(-pose[2])  # All BASE02 goals have yaw zero.
                        if abs(error) <= self.config['yaw_goal_tolerance_rad']:
                            self._terminal(robot, 'succeeded')
                            continue
                        turn = np.clip(error, -dt*self.config['max_angular_rad_s'], dt*self.config['max_angular_rad_s'])
                        pose[2] = angle(pose[2]+turn)
                        continue
                    if self.sim-goal['started'] >= self.config['navigation_timeout_sim_s']:
                        self._terminal(robot, 'aborted')
                        continue
                    points = goal['waypoints']
                    while points and np.linalg.norm(points[0]-pose[:2]) < .025:
                        points.pop(0)
                    waypoint = points[0] if points else goal['target']
                    delta = waypoint-pose[:2]
                    error = angle(math.atan2(delta[1], delta[0])-pose[2])
                    turn = np.clip(error, -dt*self.config['max_angular_rad_s'], dt*self.config['max_angular_rad_s'])
                    pose[2] = angle(pose[2]+turn)
                    if abs(error) > .20:
                        continue
                    distance = min(dt*self.config['max_linear_m_s'], np.linalg.norm(delta))
                    proposed = pose[:2]+distance*np.array([math.cos(pose[2]), math.sin(pose[2])])
                    samples = [pose[:2]+t*(proposed-pose[:2]) for t in (.25, .5, .75, 1.)]
                    safe = all(self.world.clear(p, self.config['radius_m']) and all(
                        np.linalg.norm(p-other[:2]) >= self.config['min_pair_m']
                        for name, other in self.poses.items() if name != robot) for p in samples)
                    if safe:
                        pose[:2] = proposed
                        self.paths[robot] += distance
                    else:
                        self.safe_blocks += 1
                # Sequential proposals are not themselves a simultaneous swept
                # safety certificate. Stop all translations on a joint conflict;
                # retain goals, yaw rotations and the common timeout lifecycle.
                if any(swept_pair_distance(old[a][:2], self.poses[a][:2], old[b][:2], self.poses[b][:2])
                       < self.config['min_pair_m'] for i, a in enumerate(ROBOTS) for b in ROBOTS[i+1:]):
                    for robot in ROBOTS:
                        self.paths[robot] -= float(np.linalg.norm(self.poses[robot][:2]-old[robot][:2]))
                        self.poses[robot][:2] = old[robot][:2]
                    self.safe_blocks += 1
                self.sim += dt
                for robot in ROBOTS:
                    change = self.poses[robot]-old[robot]
                    self.velocity[robot][:2] = change[:2]/dt
                    self.velocity[robot][2] = angle(change[2])/dt
                self._scan_all()
                self._record()
                coverage = self.coverage()
                for threshold in (.9, .95):
                    if coverage >= threshold:
                        self.coverage_times.setdefault(str(threshold), self.sim)
                if coverage >= .95:
                    self.done_completion = True
                    break
            return self.snapshot()

    def _record(self):
        pairs = [np.linalg.norm(self.poses[a][:2]-self.poses[b][:2])
                 for i, a in enumerate(ROBOTS) for b in ROBOTS[i+1:]]
        self.minimum_pair = min(self.minimum_pair, *pairs)
        self.trajectory.append(dict(sim=self.sim, poses={r: p.tolist() for r, p in self.poses.items()},
                                    velocities={r: v.tolist() for r, v in self.velocity.items()}))

    def coverage(self):
        reference = self.world.reference_free
        return float(np.count_nonzero((self.shared >= 0) & reference)/np.count_nonzero(reference))

    def snapshot(self):
        self.ledger.add('backend_snapshot')
        return dict(sim=self.sim, map=dict(cells=self.shared.copy(), resolution=self.world.resolution,
                                          origin=self.world.origin, stamp=self.sim),
                    robots={r: dict(pose=tuple(p), stamp=self.sim, velocity=tuple(self.velocity[r]))
                            for r, p in self.poses.items()}, events=list(self.events),
                    reason='natural_complete' if self.done_completion else None,
                    completion=(dict(reference_coverage=self.coverage(), threshold=.95,
                                     fixed_reference_cells=int(self.world.reference_free.sum()))
                                if self.done_completion else None))

    def stop(self, reason):
        with self.ledger.call('backend_stop', reason=reason):
            for robot in tuple(self.goals):
                self._terminal(robot, 'canceled')
            for velocity in self.velocity.values():
                velocity[:] = 0
            self._record()
            # Kinematic stop only; this is not the accepted Gazebo stop certificate.
            return not self.goals and all(np.array_equal(v, np.zeros(3)) for v in self.velocity.values())
