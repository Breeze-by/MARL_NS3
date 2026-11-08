"""Evaluator-only static reference and received OccupancyGrid metrics; no ROS node."""
import math
import numpy as np
from scipy.ndimage import distance_transform_edt
from multi_robot_exploration.rl_world import ProjectedWorld


def load_reference(world_path, assets, positions, require_closed=True):
    world = ProjectedWorld(world_path, assets, 'A', reference_positions=positions)
    touched = [int(np.count_nonzero(side)) for side in (
        world.reference_free[0], world.reference_free[-1],
        world.reference_free[:, 0], world.reference_free[:, -1])]
    if require_closed and any(touched):
        raise ValueError('Spawn-connected task component touches projection boundary: '+str(touched))
    return world, touched


def sample_received(cells, resolution, origin_xy_yaw, reference):
    """Reference cell centres, actual received-grid orientation, no fitted shift."""
    rows, columns = np.indices(reference.shape)
    x = reference.origin[0]+(columns+.5)*reference.resolution
    y = reference.origin[1]+(rows+.5)*reference.resolution
    ox, oy, yaw = origin_xy_yaw
    dx, dy = x-ox, y-oy
    cosine, sine = math.cos(yaw), math.sin(yaw)
    c = np.floor((cosine*dx+sine*dy)/resolution).astype(int)
    r = np.floor((-sine*dx+cosine*dy)/resolution).astype(int)
    valid = (r >= 0) & (r < cells.shape[0]) & (c >= 0) & (c < cells.shape[1])
    sampled = np.full(reference.shape, -1, dtype=np.int16)
    sampled[valid] = cells[r[valid], c[valid]]
    return sampled


def measure(sampled, reference):
    reachable = reference.reference_free
    physical_obstacles = reference.obstacles
    free, occupied = sampled == 0, sampled == 100
    correct = free & reachable
    denominator = int(np.count_nonzero(reachable))
    if not denominator:
        raise ValueError('No reachable free reference cells')
    wrong_free = free & physical_obstacles
    predicted_free = int(np.count_nonzero(free))
    truth_distance = distance_transform_edt(~physical_obstacles)*reference.resolution
    occupied_errors = truth_distance[occupied]
    known_truth_obstacles = physical_obstacles & (sampled >= 0)
    observed_obstacle_count = int(np.count_nonzero(known_truth_obstacles))
    predicted_distance = distance_transform_edt(~occupied)*reference.resolution if occupied.any() else None
    obstacle_recall = (None if not observed_obstacle_count else
        0. if predicted_distance is None else float(np.count_nonzero(
            known_truth_obstacles & (predicted_distance <= .10)))/observed_obstacle_count)
    precision = None if not predicted_free else 1-float(np.count_nonzero(wrong_free))/predicted_free
    median = None if not occupied_errors.size else float(np.median(occupied_errors))
    p95 = None if not occupied_errors.size else float(np.percentile(occupied_errors, 95))
    warnings = []
    if precision is not None and precision < .95:
        warnings.append('free_precision_below_0.95')
    if median is not None and median > .10:
        warnings.append('occupied_alignment_median_above_0.10m')
    if p95 is not None and p95 > .25:
        warnings.append('occupied_alignment_p95_above_0.25m')
    if obstacle_recall is not None and obstacle_recall < .80:
        warnings.append('known_obstacle_recall_0.10m_below_0.80')
    assessed = occupied_errors.size >= 20 and obstacle_recall is not None
    area = reference.resolution**2
    return dict(reference_free_cells=denominator, reference_free_area_m2=denominator*area,
        correct_free_cells=int(np.count_nonzero(correct)), coverage=float(np.count_nonzero(correct))/denominator,
        correct_free_area_m2=float(np.count_nonzero(correct))*area,
        unknown_reachable_area_m2=float(np.count_nonzero((sampled < 0) & reachable))*area,
        false_occupied_reachable_area_m2=float(np.count_nonzero(occupied & reachable))*area,
        false_free_physical_area_m2=float(np.count_nonzero(wrong_free))*area,
        free_precision_physical=precision, predicted_occupied_cells=int(occupied_errors.size),
        occupied_alignment_median_m=median, occupied_alignment_p95_m=p95,
        known_truth_obstacle_cells=observed_obstacle_count,
        known_obstacle_recall_within_0_10m=obstacle_recall,
        map_quality_warnings=warnings,
        map_quality_valid=bool(assessed and not warnings),
        alignment_assessment='unassessed_insufficient_occupied_evidence' if not assessed else 'warning' if warnings else 'within_predeclared_diagnostics')


def thresholds(curve, start, levels=(.5, .8, .9, .95, .98), require_quality=False):
    return {str(level): next((dict(elapsed_sim_s=row['receipt_sim']-start,
        receipt_sim=row['receipt_sim'], initially_reached=row['receipt_sim']==start)
        for row in curve if row['coverage'] >= level and
            (not require_quality or row['map_quality_valid'])), None) for level in levels}
