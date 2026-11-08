"""One static a/b/c ablation and directed fixtures; no model/sensor/env execution."""
from collections.abc import Mapping
import json
import math
from pathlib import Path
import subprocess
import sys
import types
import numpy as np

WS=Path(__file__).resolve().parent.parent;ROOT=WS.parents[1]
sys.path.insert(0,str(WS/'src/multi_robot_exploration'))
from multi_robot_exploration import allocation,frontier
from multi_robot_exploration.allocation import Allocator,observed_approach,APPROACH_CONTRACT
from multi_robot_exploration.rl_backend import route


def module(source,name):
    m=types.ModuleType('multi_robot_exploration.'+name);sys.modules[m.__name__]=m
    exec(compile(source,'<'+name+'>','exec'),m.__dict__);return m


def plain(v):
    if isinstance(v,Mapping):return {k:plain(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [plain(x) for x in v]
    if isinstance(v,np.ndarray):return v.tolist()
    return v


def run():
    output=ROOT/'rl-04/evidence/approach-static-01';output.mkdir(exist_ok=False)
    production=Path(allocation.__file__).read_text()
    reference=module(subprocess.check_output(['git','-C',str(WS),'show',
        '991bba0bf3a9d75ac36e1674e1510b60c560f6ee:src/multi_robot_exploration/multi_robot_exploration/allocation.py'],text=True),'_rl04_ref')
    assert production.count('if approach_mode and not free and shared_free')==1
    only_legal=module(production.replace('if approach_mode and not free and shared_free',
        'if False and not free and shared_free'),'_rl04_legal_only')
    assert production.count('if approach_mode else frontier.fGroups(groups)')==1
    original_top5=module(production.replace('if approach_mode else frontier.fGroups(groups)',
        'if False else frontier.fGroups(groups)'),'_rl04_approach_old_top5')
    stages=json.loads((ROOT/'rl-04/evidence/candidate-stages-02/result.json').read_text())
    folders={}
    for path in (ROOT/'rl-03/runs/test-01').glob('*/summary.json'):
        s=json.loads(path.read_text())
        if s['policy']=='rl':folders[(s['map'],s['seed'])]=path.parent
    results=[];legacy_comparisons=0;checked_targets=0
    for case in stages['cases']:
        name=case['robot'];folder=folders[(case['map'],case['seed'])]
        intent=json.loads((folder/'intents.jsonl').read_text().splitlines()[0]);obs=intent['observation']
        cells=np.load(folder/'observed-grids.npz')['cells'][0]
        local=np.load(folder/'final-local-maps.npz')[name]
        robot=next(r for r in obs['robots'] if r['id']==name)
        res=obs['map']['resolution'];ox,oy=obs['map']['origin']
        def cell(point):return (math.floor((point[1]-oy)/res),math.floor((point[0]-ox)/res))
        start=cell(robot['pose']);inflated=frontier.costmap(local,*reversed(local.shape),res)
        def setup(cls,mode):
            a=cls(robot_ids=(name,),local_goal_valid=lambda r,x,y:bool(local[cell((x,y))]==0),
                candidate_mode=mode,local_navigation_grid=lambda *args:local,navigation_path_budget_m=90*.26)
            a.update_map(cells,res,(ox,oy),obs['map']['stamp']);a.update_robot(name,tuple(robot['pose']),0.,(0.,0.,0.))
            return a.get_observation()
        for mode in ('legacy','rl03_local_v1'):
            assert plain(setup(reference.Allocator,mode))==plain(setup(Allocator,mode))
            legacy_comparisons+=1
        prefix=[];row=('tb1','tb2','tb3').index(name)
        for i,choice in enumerate(intent['action'][:row]):
            if choice>=0 and intent['masks'][i][choice]:prefix.append(obs['candidates'][choice]['position'])
        variants={}
        for label,cls in [('a_legal_before_top5_only',only_legal.Allocator),
                          ('b_approach_original_top5',original_top5.Allocator),('c_approach_legal_unique_top5',Allocator)]:
            observed=setup(cls,'rl04_approach_v1');candidates=observed['candidates']
            assert observed['contract']==APPROACH_CONTRACT and len(candidates)<=5
            assert all(math.dist(a['position'],b['position'])>=.2 for i,a in enumerate(candidates) for b in candidates[i+1:])
            for candidate in candidates:
                target=cell(candidate['position']);path=route(local,start,target,res)
                assert path is not None and local[target]==0 and candidate['valid']
                length=sum(math.dist(p,q)*res for p,q in zip(path,path[1:]))
                assert math.isclose(length,candidate['path_cost_estimate_m'],abs_tol=1e-10) and length<=90*.26
                endpoint=cell(candidate['shared_frontier_position'])
                shared_route=route(cells,start,endpoint,res);assert shared_route is not None
                if candidate['kind']=='approach':
                    assert candidate['remaining_shared_path_m']>0 and math.dist(candidate['position'],robot['pose'][:2])>.25
                    assert candidate['unknown_boundary_cells'] and all(local[tuple(p)]==-1 and inflated[tuple(p)]<0 for p in candidate['unknown_boundary_cells'])
                else:assert candidate['position']==candidate['shared_frontier_position'] and candidate['remaining_shared_path_m']==0.
                checked_targets+=1
            variants[label]=dict(raw_candidates=len(candidates),
                conditional_against_recorded_v1_prefix=sum(not any(math.dist(c['position'],p)<.2 for p in prefix) for c in candidates),
                candidates=[dict(group=c['group_id'],kind=c['kind'],position=c['position'],local_path_m=c['path_cost_estimate_m'],
                    associated_frontier=c['shared_frontier_position'],remaining_shared_path_m=c['remaining_shared_path_m']) for c in candidates])
        results.append(dict(map=case['map'],seed=case['seed'],robot=name,
            original_v1_raw=case['rows'][0]['raw_candidates'],original_v1_conditional=case['rows'][0]['conditional_goal_options'],variants=variants))
    # Directed edge fixtures exercise the actual production helper.
    path=[(2,1),(2,2),(2,3),(2,4)];grid=np.zeros((6,6));position=lambda p:(float(p[1]),float(p[0]))
    assert observed_approach(path,grid,position,lambda p:True,(1.,2.,0.),.25) is None
    grid[2,4]=-1
    assert observed_approach(path,grid,position,lambda p:True,(1.,2.,0.),.25)[0]==(2,3)
    assert observed_approach(path,grid,position,lambda p:False,(1.,2.,0.),.25) is None
    assert observed_approach(path,grid,lambda p:(p[1]*.1,p[0]*.1),lambda p:True,(.1,.2,0.),.25) is None
    first_unknown=grid.copy();first_unknown[2,2]=-1
    assert observed_approach(path,first_unknown,position,lambda p:True,(1.,2.,0.),.25) is None
    known_wall=grid.copy();known_wall[2,2]=5
    assert observed_approach(path,known_wall,position,lambda p:True,(1.,2.,0.),.25) is None
    diagonal=[(2,1),(2,2),(3,3),(4,4)];support=np.zeros((6,6));support[2,3]=-1
    assert observed_approach(diagonal,support,position,lambda p:True,(1.,2.,0.),.25)[0]==(2,2)
    support[3,2]=5
    assert observed_approach(diagonal,support,position,lambda p:True,(1.,2.,0.),.25) is None
    all_known=np.zeros((20,20),dtype=np.int16)
    a=Allocator(robot_ids=('tb1',),candidate_mode='rl04_approach_v1',local_navigation_grid=lambda *args:all_known,navigation_path_budget_m=23.4)
    a.update_map(all_known,.05,(0.,0.),0.);a.update_robot('tb1',(.5,.5,0.),0.,(0.,0.,0.))
    assert not a.get_observation()['candidates']
    # Locally reachable frontier excluded by memory/budget cannot become approach.
    known_patch=np.full((30,30),-1,dtype=np.int16);known_patch[3:27,3:27]=0
    for budget in (.01,23.4):
        a=Allocator(robot_ids=('tb1',),candidate_mode='rl04_approach_v1',local_navigation_grid=lambda *args:known_patch,navigation_path_budget_m=budget)
        a.update_map(known_patch,.05,(0.,0.),0.);a.update_robot('tb1',(.75,.75,0.),0.,(0.,0.,0.))
        if budget>1:a.visited=[((c+.5)*.05,(r+.5)*.05) for r,c in np.argwhere(known_patch==0)]
        assert not a.get_observation()['candidates']
    result=dict(status='PASS',cases=results,legacy_and_v1_exact_comparisons=legacy_comparisons,
        independently_checked_own_paths=checked_targets,static_variants='a and b are in-memory source ablations only; c is production; no new production switches',
        joint_caveat='Conditional counts hold previously recorded v1 earlier targets fixed; not new joint policy predictions or new rollout results.',
        fixtures=['unknown route edge','no unknown/no roaming','memory denial','within existing goal tolerance',
            'first step unknown/no nontrivial local prefix','known inflated wall denial','diagonal unknown support',
            'diagonal known inflated support denial','no shared frontier','local geometric endpoint with memory/budget exclusion'],
        nn_forward=0,policy_sampling=0,world_truth_reads=0,new_sensor_scans=0,env_reset=0,env_step=0,optimizer_update=0,gazebo_start=0)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
    for r in results:print(r['map'],r['seed'],r['robot'],{k:(v['raw_candidates'],v['conditional_against_recorded_v1_prefix']) for k,v in r['variants'].items()})


if __name__=='__main__':run()
