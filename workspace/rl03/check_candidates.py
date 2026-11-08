"""Directed contract checks only: no model, world, reset, stepping or physics."""
import json
import math
from pathlib import Path
import subprocess
import sys
import types
from collections.abc import Mapping
import numpy as np

HERE=Path(__file__).resolve().parent
WORKSPACE=HERE.parent
ROOT=WORKSPACE.parents[1]
sys.path.insert(0,str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration.allocation import Allocator, LOCAL_CONTRACT, distances
from multi_robot_exploration.observations import project_local_navigation
from multi_robot_exploration.rl_backend import route


def plain(v):
    if isinstance(v,Mapping):return {k:plain(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [plain(x) for x in v]
    if isinstance(v,np.ndarray):return v.tolist()
    return v


def run():
    source=subprocess.check_output(['git','-C',str(WORKSPACE),'show',
        'b1b437e68faafbfd61daa4a175475bad17116c79:src/multi_robot_exploration/multi_robot_exploration/allocation.py'],text=True)
    ref=types.ModuleType('multi_robot_exploration._rl03_reference')
    sys.modules[ref.__name__]=ref
    exec(compile(source,'<b1b-allocation>','exec'),ref.__dict__)
    source_grid=np.array([[0,100,-1],[0,0,0]],dtype=np.int16)
    shared=dict(cells=np.zeros((2,3)),resolution=1.,origin=(0.,0.))
    projected=project_local_navigation(source_grid,1.,(2.,-3.,math.pi/2),
        (2.,-3.,math.pi/2),shared)
    assert np.array_equal(projected,source_grid)
    # Non-cancelling90degree frame rotation: target(0,0)->source(0,2),
    # target(0,1)->source(1,2), target(1,0)->source(0,1).
    rotated=project_local_navigation(source_grid,1.,(0.,0.,0.),
        (3.,0.,math.pi/2),dict(cells=np.zeros((2,2)),resolution=1.,origin=(0.,0.)))
    assert np.array_equal(rotated,np.array([[-1,0],[100,0]]))
    outside=project_local_navigation(source_grid,1.,(0.,0.,0.),(10.,0.,0.),shared)
    assert np.all(outside==-1)
    corner=np.array([[0,1],[1,0]])
    assert (1,1) not in distances(corner,(0,0),.05)
    folders=[ROOT/'rl-02/runs/formal-01/episodes/00000',
        ROOT/'rl-02/runs/formal-02/validation/02048/02-central_hub_chambers-2103-201']
    static=json.loads((ROOT/'rl-03/evidence/candidate-static-01/result.json').read_text())
    cases=[]
    for folder in folders:
        saved=json.loads((folder/'last-observed.json').read_text())
        cells=np.load(folder/'observed-grids.npz')['cells'][-1]
        local=np.load(folder/'final-local-maps.npz')
        def valid(name,x,y):
            r=math.floor((y-saved['map']['origin'][1])/saved['map']['resolution'])
            c=math.floor((x-saved['map']['origin'][0])/saved['map']['resolution'])
            return bool(local[name][r,c]==0)
        def setup(cls,**kwargs):
            a=cls(local_goal_valid=valid,**kwargs)
            a.tick(saved['sim_stamp']);a.update_map(cells,saved['map']['resolution'],saved['map']['origin'],saved['map']['stamp'])
            for r in saved['robots']:
                a.update_robot(r['id'],r['pose'],r['pose_stamp'],r['velocity'])
                for key in ('state','target','last_success','last_status','condition','task_token','action_uuid'):
                    setattr(a.robots[r['id']],{'task_token':'token','action_uuid':'uuid'}.get(key,key),r[key])
            a.visited=[e['target'] for e in saved['history'] if e['status']=='succeeded']
            a.failed={name:[e['target'] for e in saved['history'] if e['robot']==name and e['status'] in ('aborted','rejected','invalid_local_goal')] for name in a.robots}
            return a
        old=setup(ref.Allocator).get_observation()
        legacy=setup(Allocator).get_observation()
        assert plain(old)==plain(legacy)
        allocator=setup(Allocator,candidate_mode='rl03_local_v1',
            local_navigation_grid=lambda name,m:local[name],navigation_path_budget_m=90*.26)
        observation=allocator.get_observation()
        assert observation['contract']==LOCAL_CONTRACT
        # Match the previously computed B ablation, not new tuned expectations.
        for i,robot in enumerate(observation['robots']):
            expected=[g for c in static['cases'] if c['map']==json.loads((folder/'summary.json').read_text())['map'] and
                c['outcome']=='stalled_wait' for r in c['robots'] if r['robot']==robot['id'] for g in r['groups']
                if g['in_original_top5'] and g['B_has_local_executable_representative']]
            actual=[c for c in observation['candidates'] if c['robot']==robot['id']]
            assert len(expected)==len(actual)
            for c,g in zip(actual,expected):
                assert c['position']==tuple(g['B_position']) and c['valid']
                assert math.isclose(c['path_cost_estimate_m'],g['B_path_cost_m'],abs_tol=1e-10)
                legacy_c=next(v for v in legacy['candidates'] if v['robot']==robot['id'] and v['group_id']==c['group_id'])
                assert c['traditional_score']==legacy_c['traditional_score']
                start=(math.floor((robot['pose'][1]-saved['map']['origin'][1])/.05),math.floor((robot['pose'][0]-saved['map']['origin'][0])/.05))
                goal=(math.floor((c['position'][1]-saved['map']['origin'][1])/.05),math.floor((c['position'][0]-saved['map']['origin'][0])/.05))
                path=route(local[robot['id']],start,goal,.05)
                assert path is not None
                length=sum(math.dist(p,q)*.05 for p,q in zip(path,path[1:]))
                assert math.isclose(length,c['path_cost_estimate_m'],abs_tol=1e-10)
        cases.append(dict(folder=str(folder.relative_to(ROOT)),legacy_exact=True,
            valid_counts=list(observation['valid_counts']),matches_saved_B=True,proxy_route_cost_equivalent=True))
        unavailable=setup(Allocator,candidate_mode='rl03_local_v1',
            local_navigation_grid=lambda *args:None,navigation_path_budget_m=90*.26).get_observation()
        assert not unavailable['candidates']
    result=dict(status='PASS',cases=cases,rotation_translation_projection=True,
        missing_map_unknown_closed=True,no_corner_cut=True,nn_forward=0,env_reset=0,env_step=0,optimizer_update=0,gazebo_start=0)
    output=ROOT/'rl-03/evidence/candidate-code-check-01.json'
    with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':run()
