"""Replay three recorded current-contract observations, with no ROS or environment."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workspace/src/multi_robot_exploration'))


def main(output):
    import numpy as np
    import scipy
    import torch
    from multi_robot_exploration.ppo import ActorCritic,load_checkpoint
    from multi_robot_exploration.rl_ledger import Ledger

    if output.exists():raise FileExistsError(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    plan=json.loads((ROOT/'evidence/fixtures/index.json').read_text())
    checkpoint=ROOT/'policy/checkpoint-00512.pt'
    model_sha=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if model_sha!=plan['checkpoint_sha256']:raise ValueError('Unexpected model bytes')
    ledger=Ledger(output.with_suffix('.ledger.jsonl'),'release_v1_1_recorded_cpu')
    torch.set_num_threads(1)
    model=ActorCritic(ledger,hidden=128)
    metadata=load_checkpoint(checkpoint,model,optimizer=None,restore_rng=False)
    model.eval()
    before={k:v.detach().clone() for k,v in model.state_dict().items()}
    captured=[]
    hook=model.register_forward_hook(lambda module,inputs,outputs:captured.append(tuple(x.detach().numpy().copy() for x in outputs)))
    result=dict(status='RUNNING',behavior_source='76fd91cf937bd8d662302901dad063affbea3c38',
        checkpoint_sha256=model_sha,checkpoint_metadata=metadata,
        runtime=dict(python=platform.python_version(),torch=torch.__version__,numpy=np.__version__,
                     scipy=scipy.__version__,threads=torch.get_num_threads(),device='cpu'),fixtures=[])
    try:
        for fixture in plan['fixtures']:
            saved=json.loads((ROOT/fixture['event']).read_text())
            event=saved['recorded_inference'];observation=copy.deepcopy(event['observed_state_and_candidates'])
            with np.load(ROOT/fixture['npz'],allow_pickle=False) as data:
                observation['map']['cells']=data['received_shared_cells'].copy()
                start=time.perf_counter()
                with torch.no_grad():record=model.act(observation,deterministic=True)
                elapsed=time.perf_counter()-start
                checks=dict(encoded_exact=np.array_equal(record['inputs'],data['encoded_inputs']),
                    masks_exact=np.array_equal(record['masks'],data['conditional_masks']),
                    slots_exact=np.array_equal(record['slots'],data['slots']),
                    choices_exact=list(record['action'].choices)==event['raw_choices'],
                    raw_logits_match=np.allclose(captured[-1][0],data['raw_logits'],atol=plan['atol'],rtol=plan['rtol']))
                for key in ('value','logprob','entropy'):
                    checks[key+'_match']=bool(np.isclose(record[key],event[key],atol=plan['atol'],rtol=plan['rtol']))
                for robot,choice in zip(('tb1','tb2','tb3'),record['action'].choices):
                    if choice<0:continue
                    request=next(x for x in saved['actual_goal_requests'] if x['robot']==robot)
                    checks[robot+'_recorded_goal_match']=bool(np.allclose(observation['candidates'][choice]['position'],request['merge_map_target'],atol=1e-9,rtol=0))
            result['fixtures'].append(dict(name=fixture['name'],choices=list(record['action'].choices),checks=checks,wall_s=elapsed))
            if not all(checks.values()):raise ValueError('Recorded contract mismatch: '+fixture['name'])
        hook.remove()
        unchanged=all(torch.equal(before[k],v) for k,v in model.state_dict().items())
        no_gradients=all(v.grad is None for v in model.parameters())
        if not unchanged or not no_gradients:raise ValueError('Inference changed model state')
        if ledger.counts['policy_forward']!=plan['expected_forwards']:raise ValueError('Unexpected forward count')
        ledger.flush('release_replay_complete',state_unchanged=unchanged,no_gradients=no_gradients)
        result.update(status='PASS',parameters=sum(x.numel() for x in model.parameters()),
            state_unchanged=unchanged,no_gradients=no_gradients,
            calls=dict(NN_forward=ledger.counts['policy_forward'],optimizer=0,Node=0,env_reset=0,env_step=0,Action=0,Gazebo=0))
    finally:
        output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('status','runtime','calls','fixtures')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/cpu-replay.json')
    main(parser.parse_args().output)
