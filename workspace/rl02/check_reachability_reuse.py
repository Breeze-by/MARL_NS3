"""One minimal equivalence check; no NN/environment/policy rollout."""
from collections.abc import Mapping
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import types
import numpy as np

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE/'src/multi_robot_exploration'))
from multi_robot_exploration.allocation import Allocator, TraditionalPolicy, distances
from multi_robot_exploration.frontier import reachable_free_cells


def plain(value):
    if isinstance(value, Mapping):return {key: plain(item) for key,item in value.items()}
    if isinstance(value, (list,tuple)):return [plain(item) for item in value]
    if isinstance(value, np.ndarray):return value.tolist()
    return value


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(90511)
    matrices = [np.zeros((4,4)), np.eye(4), np.full((4,4),-1.)]
    for size in range(6,16):
        matrices.append(rng.choice([-1.,0.,1.],(size,size),p=[.15,.65,.20]))
    for matrix in matrices:
        start=(0,0);matrix[start]=0
        assert set(distances(matrix,start,.05)) == reachable_free_cells(matrix,start)
    commit='82450698a9d32c0e8d9a00d236693828742d0812'
    source=subprocess.check_output(['git','-C',str(WORKSPACE),'show',commit+':src/multi_robot_exploration/multi_robot_exploration/allocation.py'],text=True)
    name='multi_robot_exploration._reference_allocator'
    reference=types.ModuleType(name);sys.modules[name]=reference
    exec(compile(source,'<fixed-82450698-allocation>','exec'),reference.__dict__)
    old=WORKSPACE.parents[1]/'rl-01/evidence/gate-03'
    data=np.load(old/'scene-and-observation.npz');poses=json.loads((old/'trajectory.json').read_text())[-1]['poses']
    observations=[];timing=[];choices=[]
    for cls,policy in [(reference.Allocator,reference.TraditionalPolicy()),(Allocator,TraditionalPolicy())]:
        allocator=cls();allocator.tick(20.)
        allocator.update_map(data['observed'],.05,tuple(data['origin']),20.)
        for robot,pose in poses.items():allocator.update_robot(robot,tuple(pose),20.,(0.,0.,0.))
        stamp=time.perf_counter();obs=allocator.get_observation();timing.append(time.perf_counter()-stamp)
        observations.append(plain(obs));choices.append(policy.select(obs).choices)
    assert observations[0] == observations[1]
    assert choices[0] == choices[1]
    from multi_robot_exploration.ppo import encode
    assert np.array_equal(encode(observations[0]),encode(observations[1]))
    result=dict(status='PASS',controlled_grid_cases=len(matrices),full_observation_exact=True,
        original_traditional_choices_equal=True,encoded_features_exact=True,
        original_observation_wall_s=timing[0],reuse_observation_wall_s=timing[1],
        single_timing_only=True,nn_forward=0,env_reset=0,env_step=0,optimizer_update=0,
        allocator_observation_calls=2,scope='Previously seen RL01 map only; unchanged frontier functions/scoring/distance/physics/reward')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    run(WORKSPACE.parents[0]/'evidence/reachability-reuse-01')
