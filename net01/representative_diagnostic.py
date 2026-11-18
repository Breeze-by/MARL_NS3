"""Explicit opt-in read-only original representative-selection summaries."""
import builtins
from contextlib import contextmanager
import inspect
import math

# Existing selected configuration: Smac tolerance + Position XY tolerance +
# owned-goal translational progress radius. Diagnosticonly, never selection.
USEFUL_NOMINAL_DISTANCE_M=.5+.25+.5

@contextmanager
def allocation_min_scope(records):
    from multi_robot_exploration import allocation
    missing=object();previous=allocation.__dict__.get('min',missing)
    original_min=builtins.min if previous is missing else previous
    expected_code=allocation.Allocator.get_observation.__code__
    def observe_min(*args,**kwargs):
        selected=original_min(*args,**kwargs)  # Originalkey evaluated exactlyonce.
        frame=inspect.currentframe().f_back
        try:
            if (frame.f_code is expected_code and args and frame.f_locals.get('approach_mode')
                    and not frame.f_locals.get('free') and args[0] is frame.f_locals.get('shared_free')):
                local=frame.f_locals;points=args[0];costs=local['path_costs']
                nearest=builtins.min(points,key=lambda point:(costs[point],point))
                grid=local['m'];resolution=local['res'];ox,oy=grid['origin'];allocator=local['self']
                def shared_world(point):return ((point[1]+.5)*resolution+ox,(point[0]+.5)*resolution+oy)
                records.append(dict(summary_kind='shared_endpoint_reference',robot=local['robot'].name,
                    robot_state=local['robot'].state,group_id=local['group_id'],decision_id=allocator.decision_id,
                    map_version=allocator.map_version,observed_allocator_sim=allocator.now,map_stamp=grid['stamp'],
                    resolution=resolution,origin=grid['origin'],shared_free_n=len(points),
                    original_shared_endpoint_rc=tuple(map(int,selected)),original_shared_endpoint_position=shared_world(selected),
                    original_shared_endpoint_path_cost_m=float(costs[selected]),
                    minimum_path_shared_endpoint_rc=tuple(map(int,nearest)),minimum_path_shared_endpoint_position=shared_world(nearest),
                    minimum_path_shared_endpoint_cost_m=float(costs[nearest]),cost_table='path_costs',
                    scope='Shared reachable reference only; neither endpoint nor alternative bridge is certified local admissible. No observed_approach/admissible/TF/peer recomputation; original centroid endpoint and middle Goal unchanged.'))
            if frame.f_code is expected_code and args and args[0] is frame.f_locals.get('free'):
                local=frame.f_locals;free=args[0];costs=local['local_paths'] if local['local_paths'] is not None else local['path_costs']
                nearest=builtins.min(free,key=lambda point:(costs[point],point))
                node=local['self'];grid=local['m'];resolution=local['res'];ox,oy=grid['origin']
                def world(point):return ((point[1]+.5)*resolution+ox,(point[0]+.5)*resolution+oy)
                useful=[point for point in free if math.dist(world(point),local['robot'].pose[:2])>=USEFUL_NOMINAL_DISTANCE_M]
                useful_nearest=(builtins.min(useful,key=lambda point:(costs[point],point)) if useful else None)
                useful_summary=(None if useful_nearest is None else dict(rc=tuple(map(int,useful_nearest)),position=world(useful_nearest),cost_m=float(costs[useful_nearest]),nominal_euclidean_from_received_pose_m=math.dist(world(useful_nearest),local['robot'].pose[:2])))
                records.append(dict(robot=local['robot'].name,robot_state=local['robot'].state,group_id=local['group_id'],decision_id=node.decision_id,map_version=node.map_version,observed_allocator_sim=node.now,map_stamp=grid['stamp'],resolution=resolution,origin=grid['origin'],kind=local['metadata'].get('kind','frontier'),free_n=len(free),original_local_admissible_applied=local['local_paths'] is not None,chosen_rc=tuple(map(int,selected)),chosen_position=world(selected),chosen_cost_m=float(costs[selected]),minimum_cost_rc=tuple(map(int,nearest)),minimum_cost_position=world(nearest),minimum_cost_m=float(costs[nearest]),useful_nominal_distance_m=USEFUL_NOMINAL_DISTANCE_M,useful_threshold_basis='originalSmac.5+PositionXY.25+translationprogress.5',useful_free_n=len(useful),useful_minimum_cost=useful_summary,cost_table='local_paths' if local['local_paths'] is not None else 'path_costs',scope='Original finalfree list/costdictionary only. No shared_free referenceendpoint, no re-evaluation of key/admissible/TF/peer/planner callbacks; not a replacementtarget.'))
        finally:del frame
        return selected  # Same original object, never nearest.
    allocation.min=observe_min
    try:yield
    finally:
        if previous is missing:del allocation.__dict__['min']
        else:allocation.min=previous

def observe_original(node, original, retained_records, *args, **kwargs):
    with node.lock:
        raw=[]
        with allocation_min_scope(raw):
            observation=original(*args,**kwargs)
        # Retain only the original <=15 returned candidates; each may carry
        # final-free plus shared-reference summaries (<=30 rows per decision).
        # No complete free arrays or discarded rawgroups.
        for record in raw:
            if record.get('summary_kind')=='shared_endpoint_reference':
                matches=[c['index'] for c in observation['candidates'] if c['robot']==record['robot'] and c['group_id']==record['group_id'] and c.get('kind')=='approach' and tuple(c['shared_frontier_position'])==record['original_shared_endpoint_position']]
                targets=[dict(index=c['index'],position=c['position'],path_cost_estimate_m=c['path_cost_estimate_m'],remaining_shared_path_m=c['remaining_shared_path_m']) for c in observation['candidates'] if c['index'] in matches]
                if matches:retained_records.append(dict(record,returned_candidate_indices=matches,retained_approach_middle_goals=targets))
            else:
                matches=[c['index'] for c in observation['candidates'] if c['robot']==record['robot'] and c['group_id']==record['group_id'] and tuple(c['position'])==record['chosen_position']]
                if matches:retained_records.append(dict(record,returned_candidate_indices=matches))
        return observation


VERSION='read-only-retained-representatives-v1'
CONTRACT_FILE='config/NAVIGATION_REPRESENTATIVE_DIAGNOSTIC_V1.json'

def load_contract(version):
    import json
    from pathlib import Path
    contract=json.loads((Path(__file__).resolve().parent/CONTRACT_FILE).read_text())
    if version!=VERSION or contract['revision']!=version:
        raise ValueError('Unknown representative diagnostic revision')
    return contract

def install_representative_diagnostic(node, contract, profile):
    import json
    import os
    from pathlib import Path
    original=node.allocator.get_observation
    records=[]
    def observed(*args,**kwargs):
        return observe_original(node,original,records,*args,**kwargs)
    node.allocator.get_observation=observed
    directory=Path(node.events.name).parent
    def finish_recording():
        with node.lock:
            (directory/'candidate-representatives.json').write_text(json.dumps(dict(
                pid=os.getpid(),execution_profile=profile['id'],revision=VERSION,contract=contract,
                performance_cohort=False,diagnostic_only=True,records=records,
                observation_scope='Received allocator map/pose and already computed cost tables; original chosen points unchanged. No physical AoI or alternative admissibility proof.'
            ),indent=2)+'\n')
    node._finish_representative_diagnostic_recording=finish_recording
