"""Sparse implementation equivalence to fixed RL01, without policy/env rollout."""
from collections.abc import Mapping
import json
from pathlib import Path
import subprocess
import sys
import time
import types
import numpy as np

WORKSPACE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration.allocation import Allocator,TraditionalPolicy,distances
from multi_robot_exploration.frontier import reachable_free_cells
from multi_robot_exploration.joint import slot_mask
from multi_robot_exploration.ppo import encode


def plain(value):
    if isinstance(value,Mapping):return {k:plain(v)for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [plain(v)for v in value]
    if isinstance(value,np.ndarray):return value.tolist()
    return value


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    source=subprocess.check_output(['git','-C',str(WORKSPACE),'show','82450698a9d32c0e8d9a00d236693828742d0812:src/multi_robot_exploration/multi_robot_exploration/allocation.py'],text=True)
    name='multi_robot_exploration._sparse_reference'
    reference=types.ModuleType(name);sys.modules[name]=reference
    exec(compile(source,'<fixed-82450698-allocation>','exec'),reference.__dict__)
    rng=np.random.default_rng(90512)
    cases=[np.zeros((1,1)),np.zeros((4,4)),np.eye(4),np.full((4,4),-1.),np.array([[0.,1.],[1.,0.]])]
    for size in range(5,20):cases.append(rng.choice([-1.,0.,5.],(size,size),p=[.15,.65,.20]))
    max_error=0.;double_exact=True
    for matrix in cases:
        start=(0,0);matrix[start]=0
        old=reference.distances(matrix,start,.05);new=distances(matrix,start,.05)
        assert old.keys()==new.keys() and set(new)==reachable_free_cells(matrix,start)
        error=max(abs(old[k]-new[k])for k in old);max_error=max(max_error,error)
        double_exact &= old==new
        assert error<=1e-10
    old_root=WORKSPACE.parents[1]/'rl-01/evidence/gate-03'
    data=np.load(old_root/'scene-and-observation.npz');poses=json.loads((old_root/'trajectory.json').read_text())[-1]['poses']
    observations=[];timing=[];choices=[]
    for cls,policy in [(reference.Allocator,reference.TraditionalPolicy()),(Allocator,TraditionalPolicy())]:
        a=cls();a.tick(20.);a.update_map(data['observed'],.05,tuple(data['origin']),20.)
        for robot,pose in poses.items():a.update_robot(robot,tuple(pose),20.,(0.,0.,0.))
        start=time.perf_counter();obs=a.get_observation();timing.append(time.perf_counter()-start)
        observations.append(plain(obs));choices.append(policy.select(obs).choices)
    original,current=observations
    assert choices[0]==choices[1]
    for before,after in zip(original['candidates'],current['candidates']):
        error=abs(before['path_cost_estimate_m']-after['path_cost_estimate_m']);max_error=max(max_error,error)
        double_exact &= before['path_cost_estimate_m']==after['path_cost_estimate_m']
        assert error<=1e-10
    assert np.array_equal(encode(original),encode(current))
    # Only the derived double-precision path cost may differ by roundoff.
    for obs in observations:
        for candidate in obs['candidates']:candidate.pop('path_cost_estimate_m')
    assert original==current
    prefix=[]
    for row in range(3):
        old_mask=slot_mask(original,row,prefix);new_mask=slot_mask(current,row,prefix)
        assert np.array_equal(old_mask,new_mask)
        slot=int(np.flatnonzero(old_mask)[0]);prefix.append(-1 if slot==15 else -2 if slot==16 else slot)
    result=dict(status='PASS',controlled_grid_cases=len(cases),all_reachable_sets_exact=True,
        full_non_cost_observation_exact=True,candidate_order_position_valid_score_exact=True,
        traditional_action_exact=True,conditional_masks_exact=True,float32_encoding_exact=True,
        double_cost_byte_exact=bool(double_exact),max_double_cost_abs_error_m=max_error,
        original_observation_wall_s=timing[0],sparse_observation_wall_s=timing[1],single_timing_only=True,
        nn_forward=0,env_reset=0,env_step=0,optimizer_update=0,allocator_observation_calls=2,
        graph_source='same received matrix==0; same eight moves and corner rule; no truth clearance')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':run(WORKSPACE.parents[0]/'evidence/sparse-distances-01')
