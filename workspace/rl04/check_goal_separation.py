"""Directed centre-reservation contract check; fixed-logit sampler, no trained policy/env."""
from collections.abc import Mapping
import json
from pathlib import Path
import subprocess
import sys
import types
import numpy as np
import torch

WS=Path(__file__).resolve().parent.parent;ROOT=WS.parents[1]
sys.path.insert(0,str(WS/'src/multi_robot_exploration'))
from multi_robot_exploration.allocation import Allocator,JointAction,frozen
from multi_robot_exploration.joint import candidate_mask,slot_mask,JointTraditionalPolicy
from multi_robot_exploration.ppo import ActorCritic
from multi_robot_exploration.observations import TASK_ROI


def plain(v):
    if isinstance(v,Mapping):return {k:plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [plain(x) for x in v]
    if isinstance(v,np.ndarray):return v.tolist()
    return v


def run():
    output=ROOT/'rl-04/evidence/goal-separation-check-01';output.mkdir(exist_ok=False)
    patch=np.full((30,30),-1,dtype=np.int16);patch[3:27,3:27]=0
    def allocator(cls,mode):
        a=cls(candidate_mode=mode,local_navigation_grid=lambda *args:patch,navigation_path_budget_m=23.4)
        a.update_map(patch,.05,(0.,0.),0.)
        for name in a.robots:a.update_robot(name,(.75,.75,0.),0.,(0.,0.,0.))
        return a
    source=subprocess.check_output(['git','-C',str(WS),'show',
        'bd835083e8f4b067c79213aa361da2151229ac78:src/multi_robot_exploration/multi_robot_exploration/allocation.py'],text=True)
    ref=types.ModuleType('multi_robot_exploration._separation_ref');sys.modules[ref.__name__]=ref;exec(compile(source,'<bd835>', 'exec'),ref.__dict__)
    for mode in ('legacy','rl03_local_v1','rl04_approach_v1'):
        a=allocator(Allocator,mode);b=allocator(ref.Allocator,mode)
        for target in (a,b):
            target.visited=[(.4,.4)];target.robots['tb1'].target=(.8,.3);target.robots['tb1'].state='active';target.robots['tb1'].started=0.
        assert plain(a.get_observation())==plain(b.get_observation())
    # Generated candidates honor active.7 while historical visits retain.2.
    a=allocator(Allocator,'rl04_approach_v2');point=a.get_observation()['candidates'][0]['position']
    a.visited=[(point[0]+.3,point[1])]
    assert point in [c['position'] for c in a.get_observation()['candidates'] if c['robot']=='tb2']
    a.robots['tb1'].target=(point[0]+.3,point[1]);a.robots['tb1'].state='active';a.robots['tb1'].started=0.
    o=a.get_observation()
    assert all(np.linalg.norm(np.array(c['position'])-a.robots['tb1'].target)>=.7 for c in o['candidates'] if c['robot']=='tb2')
    def fixture(mode):
        a=allocator(Allocator,mode);o=dict(a.get_observation())
        values=[('tb1',(1.,1.),10),('tb2',(1.4,1.),10),('tb2',(3.,1.),9),('tb2',(4.,1.),8),('tb3',(7.,1.),10)]
        o['candidates']=tuple(dict(index=i,robot=r,position=p,valid=True,local_map_valid=True,reachable=True,
            path_cost_estimate_m=1.,information_gain_proxy_m2=1.,traditional_eligible=True,traditional_score=score)
            for i,(r,p,score) in enumerate(values))
        o['action_mask']=tuple(tuple(c['robot']==name for c in o['candidates']) for name in a.robots)
        return a,frozen(o)
    a,o=fixture('rl04_approach_v2')
    assert not candidate_mask(o,1,(0,))[1] and candidate_mask(o,1,(0,))[2]
    traditional=JointTraditionalPolicy().select(o);assert traditional.choices==(0,2,4)
    proposals,rejected=a.apply(o,traditional);assert len(proposals)==3 and not rejected
    bad,o=fixture('rl04_approach_v2');_,rejected=bad.apply(o,JointAction(o['decision_id'],o['map_version'],(0,1,4)))
    assert rejected['tb2']=='target_conflict'
    old,o_old=fixture('rl04_approach_v1');assert candidate_mask(o_old,1,(0,))[1]
    assert JointTraditionalPolicy().select(o_old).choices==(0,1,4)
    # Exercise actual act/recompute with fixed logits, not a neural network.
    class Fixed:
        act=ActorCritic.act;recompute=ActorCritic.recompute;encode=ActorCritic.encode
        task_roi=TASK_ROI
        def __init__(self):self.stub_forward_calls=0
        def __call__(self,inputs):
            self.stub_forward_calls+=1
            logits=torch.zeros((len(inputs),3,17));logits[:,1,1]=10.;logits[:,1,2]=9.
            return logits,torch.zeros(len(inputs))
    _,o=fixture('rl04_approach_v2');model=Fixed();sample=model.act(o,deterministic=True)
    assert sample['action'].choices==(0,2,4) and not sample['masks'][1,1]
    logprob,_,_=model.recompute(torch.from_numpy(sample['inputs'])[None],torch.from_numpy(sample['slots'])[None],torch.from_numpy(sample['masks'])[None])
    assert abs(float(logprob[0])-sample['logprob'])<1e-6
    result=dict(status='PASS',old_modes_exact=3,generated_active_clearance_m=.7,history_radius_remains_m=.2,
        prefix_mask_allocator_and_traditional_agree=True,sampler_saved_masks_recompute_logprob_equal=True,
        synthetic_sampler_calls=1,fixed_logit_stub_forward_calls=model.stub_forward_calls,
        real_neural_forward=0,trained_model_load=0,env_reset=0,env_step=0,optimizer_update=0,ros_nodes=0,gazebo_start=0,
        caveat='Target centres.7 does not guarantee every.25-tolerance stop configuration safe and does not solve far-endpoint opposing routes.')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':run()
