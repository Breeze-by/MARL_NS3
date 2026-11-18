"""Explicit A opt-in: direct-frontier representative inside original admissible free."""
import builtins
from contextlib import contextmanager
import inspect
import math

# Existing tolerances/progress radius, not a tuned navigation radius.
MIN_NOMINAL_DISTANCE_M=.5+.25+.5

@contextmanager
def representative_scope(records):
    from multi_robot_exploration import allocation
    missing=object();previous=allocation.__dict__.get('min',missing)
    original_min=builtins.min if previous is missing else previous
    expected_code=allocation.Allocator.get_observation.__code__
    def selected_min(*args,**kwargs):
        selected=original_min(*args,**kwargs)
        frame=inspect.currentframe().f_back
        try:
            local=frame.f_locals
            if (frame.f_code is expected_code and args and args[0] is local.get('free')
                    and local.get('local_paths') is not None
                    and local['metadata'].get('kind','frontier')=='frontier'):
                free=args[0];costs=local['local_paths'];res=local['res'];ox,oy=local['m']['origin']
                def world(point):return ((point[1]+.5)*res+ox,(point[0]+.5)*res+oy)
                useful=[point for point in free if math.dist(world(point),local['robot'].pose[:2])>=MIN_NOMINAL_DISTANCE_M]
                best=builtins.min(useful,key=lambda point:(costs[point],point)) if useful else None
                replacement=best if best is not None and costs[best]<costs[selected] else selected
                records.append(dict(robot=local['robot'].name,group_id=local['group_id'],decision_id=local['self'].decision_id,
                    map_version=local['self'].map_version,kind='frontier',free_n=len(free),useful_n=len(useful),
                    original_rc=tuple(map(int,selected)),original_position=world(selected),original_cost_m=float(costs[selected]),
                    returned_rc=tuple(map(int,replacement)),returned_position=world(replacement),returned_cost_m=float(costs[replacement]),
                    replaced=replacement is not selected,nominal_distance_m=math.dist(world(replacement),local['robot'].pose[:2]),
                    returned_in_original_free=replacement in free,threshold_m=MIN_NOMINAL_DISTANCE_M))
                return replacement
        finally:del frame
        return selected
    allocation.min=selected_min
    try:yield
    finally:
        if previous is missing:del allocation.__dict__['min']
        else:allocation.min=previous

def observe_original(node,original,records,*args,**kwargs):
    with node.lock:
        with representative_scope(records):
            return original(*args,**kwargs)


VERSION='direct-frontier-meaningful-mincost-v1'
CONTRACT_FILE='config/NAVIGATION_FRONTIER_REPRESENTATIVE_V1.json'

def load_contract(version):
    import json
    from pathlib import Path
    contract=json.loads((Path(__file__).resolve().parent/CONTRACT_FILE).read_text())
    if version!=VERSION or contract['revision']!=version:
        raise ValueError('Unknown frontier representative revision')
    return contract

def install_frontier_representative(node,contract,profile):
    import json
    import os
    from pathlib import Path
    original=node.allocator.get_observation
    records=[]
    def observed(*args,**kwargs):
        raw=[]
        observation=observe_original(node,original,raw,*args,**kwargs)
        for record in raw:
            indices=[c['index'] for c in observation['candidates'] if c['robot']==record['robot'] and c['group_id']==record['group_id'] and c.get('kind')=='frontier' and tuple(c['position'])==record['returned_position']]
            if indices and record['replaced']:
                records.append(dict(decision_id=record['decision_id'],map_version=record['map_version'],
                    robot=record['robot'],group_id=record['group_id'],retained_indices=indices,
                    original_position=record['original_position'],returned_position=record['returned_position'],
                    original_cost_m=record['original_cost_m'],returned_cost_m=record['returned_cost_m']))
        return observation
    node.allocator.get_observation=observed
    directory=Path(node.events.name).parent
    def finish_recording():
        with node.lock:
            (directory/'frontier-representative.json').write_text(json.dumps(dict(
                pid=os.getpid(),execution_profile=profile['id'],revision=VERSION,contract=contract,
                records=records,scope='Only actual replaced final-retained representatives, <=15/decision; temporary raw summaries discarded. New candidate input/Goal semantics; no old-logit prediction.'
            ),indent=2)+'\n')
    node._finish_frontier_representative_recording=finish_recording
