"""Predeclared RL02 static-box scenes and geometry-only pose qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import numpy as np
from scipy.ndimage import label

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
PROJECT = WORKSPACE.parent
ROOT = PROJECT.parent
sys.path.insert(0, str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration.allocation import Allocator
from multi_robot_exploration.rl_backend import KinematicBackend, ROBOTS
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.rl_world import ProjectedWorld

ROI = [-5.8, -5.6, 7.25, 5.3]
LEFT, BOTTOM, RIGHT, TOP = -5.775, -5.575, 7.225, 5.275
THICKNESS = .15


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_sha(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def layout(family, seed):
    rng = np.random.default_rng(seed)
    boxes = []

    def rectangle(x0, y0, x1, y1):
        if x1 <= x0 or y1 <= y0:
            raise ValueError('Nonpositive declared box')
        boxes.append([float(v) for v in (x0, y0, x1, y1)])

    def vertical(x, lo, hi, doors=()):
        cursor = lo
        for center, width in sorted(doors):
            rectangle(x-THICKNESS/2, cursor, x+THICKNESS/2, center-width/2)
            cursor = center+width/2
        rectangle(x-THICKNESS/2, cursor, x+THICKNESS/2, hi)

    def horizontal(y, lo, hi, doors=()):
        cursor = lo
        for center, width in sorted(doors):
            rectangle(cursor, y-THICKNESS/2, center-width/2, y+THICKNESS/2)
            cursor = center+width/2
        rectangle(cursor, y-THICKNESS/2, hi, y+THICKNESS/2)

    rectangle(LEFT, BOTTOM, RIGHT, BOTTOM+THICKNESS)
    rectangle(LEFT, TOP-THICKNESS, RIGHT, TOP)
    rectangle(LEFT, BOTTOM, LEFT+THICKNESS, TOP)
    rectangle(RIGHT-THICKNESS, BOTTOM, RIGHT, TOP)
    cx, cy = (LEFT+RIGHT)/2, (BOTTOM+TOP)/2
    if family == 'partition_grid':
        xs = np.linspace(LEFT+THICKNESS, RIGHT-THICKNESS, 4)
        ys = np.linspace(BOTTOM+THICKNESS, TOP-THICKNESS, 4)
        xs[1:3] += rng.uniform(-.25, .25, 2)
        ys[1:3] += rng.uniform(-.25, .25, 2)
        for x in xs[1:3]:
            vertical(x, ys[0], ys[-1], [((a+b)/2, 1.4) for a, b in zip(ys[:-1], ys[1:])])
        for y in ys[1:3]:
            horizontal(y, xs[0], xs[-1], [((a+b)/2, 1.4) for a, b in zip(xs[:-1], xs[1:])])
        anchor = [(xs[0]+xs[1])/2, (ys[0]+ys[1])/2]
    elif family == 'alternating_baffles':
        for index, y in enumerate(np.linspace(BOTTOM+2.1, TOP-2.1, 4)+rng.uniform(-.18, .18, 4)):
            gap = rng.uniform(2., 2.4)
            a, b = (LEFT+THICKNESS, RIGHT-gap) if index % 2 == 0 else (LEFT+gap, RIGHT-THICKNESS)
            horizontal(y, a, b)
        anchor = [cx, BOTTOM+1.]
    elif family == 'central_hub_chambers':
        half = rng.uniform(1., 1.2)
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = cx+sx*half, cy+sy*half
                xlo, xhi = sorted((x, LEFT+THICKNESS if sx < 0 else RIGHT-THICKNESS))
                ylo, yhi = sorted((y, BOTTOM+THICKNESS if sy < 0 else TOP-THICKNESS))
                if rng.integers(2):
                    vertical(x, ylo, yhi, [((ylo+yhi)/2, 1.4)])
                    horizontal(y, xlo, xhi)
                else:
                    vertical(x, ylo, yhi)
                    horizontal(y, xlo, xhi, [((xlo+xhi)/2, 1.4)])
        anchor = [cx, cy]
    elif family == 'loop_chambers':
        cx += rng.uniform(-.25, .25)
        cy += rng.uniform(-.25, .25)
        xlo, xhi, ylo, yhi = cx-3.5, cx+3.5, cy-2.7, cy+2.7
        vertical(xlo, ylo, yhi)
        vertical(xhi, ylo, yhi)
        horizontal(ylo, xlo, xhi, [(cx+rng.uniform(-.5, .5), 1.4)])
        horizontal(yhi, xlo, xhi, [(cx+rng.uniform(-.5, .5), 1.4)])
        horizontal(cy, xlo, xhi, [(cx+rng.uniform(-1.5, 1.5), 1.4)])
        anchor = [(LEFT+xlo)/2, cy]
    elif family == 'branching_corridors':
        free = [(cx-.9, BOTTOM+.25, cx+.9, TOP-.25)]
        for index, y in enumerate(np.linspace(BOTTOM+1., TOP-1., 5)+rng.uniform(-.1, .1, 5)):
            width = rng.uniform(1.45, 1.65)
            xlo, xhi = (LEFT+.25, cx+.9) if index % 2 == 0 else (cx-.9, RIGHT-.25)
            free.append((xlo, y-width/2, xhi, y+width/2))
        xs = sorted({LEFT+THICKNESS, RIGHT-THICKNESS, *(v for r in free for v in (r[0], r[2]))})
        ys = sorted({BOTTOM+THICKNESS, TOP-THICKNESS, *(v for r in free for v in (r[1], r[3]))})
        for x0, x1 in zip(xs[:-1], xs[1:]):
            for y0, y1 in zip(ys[:-1], ys[1:]):
                x, y = (x0+x1)/2, (y0+y1)/2
                if not any(a <= x <= c and b <= y <= d for a, b, c, d in free):
                    rectangle(x0, y0, x1, y1)
        anchor = [cx, cy]
    else:
        raise ValueError(family)
    return boxes, [float(v) for v in anchor]


def write_sdf(path, family, seed, boxes):
    sdf = ET.Element('sdf', version='1.6')
    world = ET.SubElement(sdf, 'world', name=f'rl02_{family}_{seed}')
    ET.SubElement(world, 'gravity').text = '0 0 -9.8'
    ground = ET.SubElement(world, 'model', name='ground_plane')
    ET.SubElement(ground, 'static').text = 'true'
    link = ET.SubElement(ground, 'link', name='ground')
    for tag in ('collision', 'visual'):
        plane = ET.SubElement(ET.SubElement(ET.SubElement(link, tag, name='ground'), 'geometry'), 'plane')
        ET.SubElement(plane, 'normal').text = '0 0 1'
        ET.SubElement(plane, 'size').text = '100 100'
    model = ET.SubElement(world, 'model', name='my_floor')
    ET.SubElement(model, 'static').text = 'true'
    for index, (x0, y0, x1, y1) in enumerate(boxes):
        link = ET.SubElement(model, 'link', name=f'wall_{index:03d}')
        ET.SubElement(link, 'pose').text = f'{(x0+x1)/2:.12g} {(y0+y1)/2:.12g} 1.25 0 0 0'
        for tag in ('collision', 'visual'):
            box = ET.SubElement(ET.SubElement(ET.SubElement(link, tag, name=f'{tag}_{index}'), 'geometry'), 'box')
            ET.SubElement(box, 'size').text = f'{x1-x0:.12g} {y1-y0:.12g} 2.5'
    # The validated projector honors saved state when present. Empty state keeps
    # generated collision transforms identical to their ordinary SDF poses.
    ET.SubElement(world, 'state', world_name=world.attrib['name'])
    ET.indent(sdf)
    ET.ElementTree(sdf).write(path, encoding='utf-8', xml_declaration=True)


def canonical_geometry(array):
    return min(array_sha(np.rot90(a, k)) for a in (array, np.fliplr(array)) for k in range(4))


def pose_qualification(world, map_seed, pose_seed, config, ledger):
    rng = np.random.default_rng(np.random.SeedSequence([map_seed, pose_seed]))
    cells = np.argwhere(world.reference_free & (world.clearance >= .40))
    attempts = []
    for attempt in range(1, 33):
        points = [world.position(p).tolist() for p in cells[rng.choice(len(cells), 3, replace=False)]]
        minimum = min(float(np.linalg.norm(np.array(a)-b)) for i, a in enumerate(points) for b in points[i+1:])
        row = dict(attempt=attempt, positions=points, minimum_pair_m=minimum)
        if minimum < 1.:
            row['rejected'] = 'initial_pair_below_1m'
        else:
            backend_config = dict(config['backend'], initial_positions=points)
            backend = KinematicBackend(world, backend_config, ledger, pose_seed)
            backend.reset()
            allocator = Allocator(local_goal_valid=backend.goal_valid, task_roi=ROI)
            allocator.update_map(backend.shared, world.resolution, world.origin, 0.)
            for robot in ROBOTS:
                allocator.update_robot(robot, tuple(backend.poses[robot]), 0., (0., 0., 0.))
            ledger.add('qualification_allocator_observation_build')
            observed = allocator.get_observation()
            row.update(initial_coverage=backend.coverage(), valid_counts=list(observed['valid_counts']))
            backend.stop('p1_geometry_only')
            if row['initial_coverage'] >= .85:
                row['rejected'] = 'initial_scan_at_least_85_percent'
            elif not all(observed['valid_counts']):
                row['rejected'] = 'some_robot_has_no_legal_initial_frontier'
            else:
                row['rejected'] = None
        attempts.append(row)
        ledger.flush('pose_qualification_attempt', map_seed=map_seed, pose_seed=pose_seed, **row)
        if row['rejected'] is None:
            return dict(seed=pose_seed, positions=points, yaw=[0., 0., 0.], attempts=attempts)
    raise RuntimeError(f'No qualified geometry-only spawn after 32 attempts: {map_seed}/{pose_seed}')


def qualify(output):
    output.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(output/'ledger.jsonl', 'p1_geometry_only')
    config = json.loads((WORKSPACE/'rl01/config.json').read_text())
    assets = ROOT/'base-01-econ/assets/gazebo_models'
    econ = WORKSPACE/'src/multi_robot/worlds/my_world.world'
    specs = [('TRAIN', 'econ', 1000, 'A'), ('TRAIN', 'econ', 1001, 'B')]
    for split, family, seeds in [('TRAIN', 'partition_grid', range(1101, 1104)),
                                 ('TRAIN', 'alternating_baffles', range(1201, 1204)),
                                 ('VAL', 'central_hub_chambers', range(2101, 2104)),
                                 ('TEST', 'loop_chambers', range(3101, 3104)),
                                 ('TEST', 'branching_corridors', range(3201, 3204))]:
        specs.extend((split, family, seed, 'A') for seed in seeds)
    maps, signatures = [], {}
    dump(output/'generation-identity.json', dict(rule_sha256=sha(HERE/'MAP_RULES.md'),
         generator_sha256=sha(__file__), projector_sha256=sha(WORKSPACE/'src/multi_robot_exploration/multi_robot_exploration/rl_world.py'),
         new_policy_rollout=0, nn_forward=0, optimizer_update=0,
         specs=specs, purpose='pre-policy static geometry and actual initial sensor qualification'))
    for split, family, seed, variant in specs:
        name = f'{family}-{variant if family == "econ" else seed}'
        target = output/name
        target.mkdir()
        if family == 'econ':
            source, reference_positions = econ, None
            boxes = None
        else:
            boxes, anchor = layout(family, seed)
            source, reference_positions = target/'world.sdf', [anchor]
            write_sdf(source, family, seed, boxes)
        with ledger.call('world_projection_build', map=name):
            world = ProjectedWorld(source, assets, variant, reference_positions=reference_positions)
        if not np.allclose(world.bounds, ROI, atol=1e-10):
            raise ValueError(f'ROI mismatch: {name}/{world.bounds}')
        nav_components, nav_count = label(world.reference_free & (world.clearance >= .38))
        # Original Econ maps retain their original component contract, with all
        # component counts reported rather than silently redefined.
        if family != 'econ' and nav_count != 1:
            dump(target/'geometry-failure.json', dict(reason='disconnected_nav_clear_region', components=nav_count))
            raise ValueError(f'{name}: {nav_count} navigable components')
        signature = canonical_geometry(world.obstacles)
        if signature in signatures:
            raise ValueError(f'Geometric duplicate: {name}/{signatures[signature]}')
        signatures[signature] = name
        np.savez_compressed(target/'projection.npz', obstacles=world.obstacles,
            lidar_obstacles=world.lidar_obstacles, reference_free=world.reference_free,
            clearance=world.clearance, origin=world.origin, resolution=world.resolution)
        row = dict(name=name, split=split, family=family, map_seed=seed, variant=variant,
            source=str(source.relative_to(ROOT)), source_sha256=sha(source), reference_positions=reference_positions,
            generated=family != 'econ', declared_box_rectangles=boxes,
            bounds=world.bounds, shape=world.shape, physical_components=int(label(world.reference_free)[1]),
            nav_clear_components=int(nav_count), reference_cells=int(world.reference_free.sum()),
            reference_area_m2=float(world.reference_free.sum()*world.resolution**2),
            canonical_geometry_sha256=signature, projection_sha256=sha(target/'projection.npz'),
            reference_mask_sha256=array_sha(world.reference_free), positions=[])
        dump(target/'geometry.json', row)
        seeds = {'TRAIN': [101, 102, 103, 104], 'VAL': [201, 202], 'TEST': [301, 302, 303]}[split]
        for pose_seed in seeds:
            row['positions'].append(pose_qualification(world, seed, pose_seed, config, ledger))
            dump(target/'geometry.json', row)
        maps.append(row)
        dump(output/'maps.partial.json', maps)
        print(json.dumps(dict(qualified=name, split=split, initial_coverages=[p['attempts'][-1]['initial_coverage'] for p in row['positions']]), allow_nan=False), flush=True)
    dump(output/'maps.json', maps)
    ledger.flush('p1_complete', maps=len(maps))
    dump(output/'result.json', dict(status='GEOMETRY PASS', maps=len(maps),
        split_counts={s: sum(m['split'] == s for m in maps) for s in ('TRAIN', 'VAL', 'TEST')},
        call_counts=dict(ledger.counts), nn_forward=0, env_step=0, optimizer_update=0,
        gazebo_load_verified=False, test_policy_rollout=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    qualify(args.output.resolve())
