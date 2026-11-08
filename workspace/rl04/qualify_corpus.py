"""One fixed physical qualification; no policy/candidate-based map selection."""
import copy
import json
import subprocess
import traceback
import numpy as np
from scipy.ndimage import label
from common import ROOT, PROJECT, WORKSPACE, dump, sha, configuration, Ledger
from maps import layout, write_sdf, canonical_geometry, array_sha, ROI
from multi_robot_exploration.rl_world import ProjectedWorld
from multi_robot_exploration.rl_backend import KinematicBackend


def qualify_pose(world, map_seed, pose_seed, config, ledger):
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
            backend = KinematicBackend(world, dict(config['backend'], initial_positions=points), ledger, pose_seed)
            backend.reset()
            row['initial_coverage'] = backend.coverage()
            if not backend.stop('rl04_geometry_initial_scan_only'):
                raise RuntimeError('Qualification stop failed')
            row['rejected'] = 'initial_scan_at_least_85_percent' if row['initial_coverage'] >= .85 else None
        attempts.append(row)
        ledger.flush('physical_pose_qualification_attempt', map_seed=map_seed, pose_seed=pose_seed, **row)
        if row['rejected'] is None:
            return dict(seed=pose_seed, positions=points, yaw=[0., 0., 0.], attempts=attempts)
    raise RuntimeError(f'No physically qualified spawn in32attempts: {map_seed}/{pose_seed}')


def run():
    output = PROJECT/'evidence/corpus-01'
    output.mkdir(exist_ok=False)
    config = configuration()
    ledger = Ledger(output/'ledger.jsonl', 'rl04_geometry_only')
    old = json.loads((ROOT/'rl-02/evidence/map-qualification-01/maps.json').read_text())
    exposed = json.loads((ROOT/'rl-03/evidence/new-test-qualification-01/maps.json').read_text())
    signatures = {r['canonical_geometry_sha256']: r['name'] for r in old+exposed}
    maps = [copy.deepcopy(r) for r in old if r['split'] == 'TRAIN']
    for r in maps:
        r['provenance'] = 'original_RL02_TRAIN_positions_reused_without_resampling'
    for r in exposed:
        row = copy.deepcopy(r)
        row.update(split='TRAIN', provenance='public_previous_RL03_TEST_promoted_to_TRAIN')
        maps.append(row)
    central = copy.deepcopy(next(r for r in old if r['name'] == 'central_hub_chambers-2103'))
    central['positions'] = [p for p in central['positions'] if p['seed'] == 202]
    central['provenance'] = 'original_public_VAL_geometry_and_qualified_202_pose_reused'
    specs = [('VAL', 'loop_chambers', 5301, [701]), ('VAL', 'branching_corridors', 5401, [701])]
    specs += [('TEST', f, s, [601, 602]) for f, seeds in
              [('loop_chambers', range(5101, 5104)), ('branching_corridors', range(5201, 5204))] for s in seeds]
    dump(output/'plan.json', dict(specs=specs, central_VAL=[central['name'], 202],
        source_commit=subprocess.check_output(['git', '-C', str(WORKSPACE), 'rev-parse', 'HEAD'], text=True).strip(),
        source_sha256=sha(__file__), generator_sha256=sha(WORKSPACE/'rl02/maps.py'),
        candidate_based_filter=False, max_spawn_attempts=32, maximum_policy_rollouts=0,
        maximum_generated_maps=8, maximum_qualified_pose_groups=14))
    try:
        for split, family, seed, pose_seeds in specs:
            name = f'{family}-{seed}'
            target = output/name
            target.mkdir()
            boxes, anchor = layout(family, seed)
            source = target/'world.sdf'
            write_sdf(source, family, seed, boxes)
            world = ProjectedWorld(source, ROOT/'base-01-econ/assets/gazebo_models', 'A', reference_positions=[anchor])
            if not np.allclose(world.bounds, ROI, atol=1e-10):
                raise ValueError('ROI mismatch')
            nav_count = label(world.reference_free & (world.clearance >= .38))[1]
            signature = canonical_geometry(world.obstacles)
            if nav_count != 1 or signature in signatures:
                dump(target/'geometry-failure.json', dict(nav_components=nav_count, duplicate_of=signatures.get(signature)))
                raise ValueError('Unqualified predeclared geometry: '+name)
            signatures[signature] = name
            np.savez_compressed(target/'projection.npz', obstacles=world.obstacles, lidar_obstacles=world.lidar_obstacles,
                reference_free=world.reference_free, clearance=world.clearance, origin=world.origin, resolution=world.resolution)
            row = dict(name=name, split=split, family=family, map_seed=seed, variant='A',
                source=str(source.relative_to(ROOT)), source_sha256=sha(source), reference_positions=[anchor],
                generated=True, declared_box_rectangles=boxes, bounds=world.bounds, shape=world.shape,
                physical_components=int(label(world.reference_free)[1]), nav_clear_components=int(nav_count),
                reference_cells=int(world.reference_free.sum()), reference_area_m2=float(world.reference_free.sum()*.05**2),
                canonical_geometry_sha256=signature, projection_sha256=sha(target/'projection.npz'),
                reference_mask_sha256=array_sha(world.reference_free), positions=[],
                provenance='predeclared_new_geometry_physical_qualification_only')
            for pose_seed in pose_seeds:
                row['positions'].append(qualify_pose(world, seed, pose_seed, config, ledger))
            dump(target/'geometry.json', row)
            maps.append(row)
            dump(output/'maps.partial.json', maps)
            print(json.dumps(dict(qualified=name, split=split,
                initial_coverages=[p['attempts'][-1]['initial_coverage'] for p in row['positions']])), flush=True)
        maps.insert(16, central)
        if [(s, sum(r['split'] == s for r in maps), sum(len(r['positions']) for r in maps if r['split'] == s))
            for s in ('TRAIN', 'VAL', 'TEST')] != [('TRAIN', 14, 44), ('VAL', 3, 3), ('TEST', 6, 12)]:
            raise ValueError('Registered corpus split/pose count mismatch')
        dump(output/'maps.json', maps)
        ledger.flush('corpus_geometry_complete', maps=len(maps))
        dump(output/'result.json', dict(status='GEOMETRY PASS', maps=len(maps), generated_maps=8,
            generated_pose_groups=14, TRAIN_maps=14, TRAIN_pairs=44, VAL_cases=3, TEST_cases=12,
            counts=dict(ledger.counts), policy_rollouts=0, nn_forward=0, env_step=0, optimizer_update=0,
            candidate_based_filter=False, gazebo_load_verified=False,
            scope='new instances of exposed public families, not structural-domain holdout'))
    except BaseException as failure:
        dump(output/'first-failure.json', dict(type=type(failure).__name__, message=str(failure), traceback=traceback.format_exc()))
        ledger.flush('qualification_failed')
        raise


if __name__ == '__main__':
    run()
