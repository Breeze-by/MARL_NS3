"""Filter prefix actor eligibility first; then apply the preregistered VAL ranking."""
import json
import numpy as np
import torch
from common import PROJECT,ROOT,dump,sha
from train import validate_checkpoint


def run():
    parent=PROJECT/'runs/formal-01'
    summary=json.loads((parent/'summary.json').read_text())
    if json.loads((parent/'process-exit.json').read_text())['exit_code']!=0:
        raise ValueError('Formal parent did not exit0')
    rollouts=[json.loads(s) for s in (parent/'rollouts.jsonl').read_text().splitlines()]
    updates=[json.loads(s) for s in (parent/'updates.jsonl').read_text().splitlines()]
    initial=torch.load(parent/'initial.pt',map_location='cpu',weights_only=False)['model']['actor.weight']
    eligible=[];excluded=[]
    for joint in (512,1024,1536,2048):
        path=parent/f'checkpoint-{joint:05d}.pt'
        checkpoint=validate_checkpoint(path,summary)
        if checkpoint['metadata']['config']['observation_contract']!='rl03-local-reachable-v1':
            raise ValueError('Checkpoint contract mismatch')
        opportunities=np.sum([r['nonforced_per_head'] for r in rollouts if r['after_joint_decisions']<=joint],axis=0)
        gradients=np.max([r['per_head_actor_weight_gradient'] for r in updates if r['after_joint_decisions']<=joint],axis=0)
        change=(checkpoint['model']['actor.weight']-initial).reshape(3,17,-1).norm(dim=(1,2)).tolist()
        actor=dict(nonforced_per_head=opportunities.tolist(),maximum_actor_gradient_per_head=gradients.tolist(),net_actor_weight_change_per_head=change)
        if not (np.all(opportunities>=20) and np.all(gradients>0) and all(v>0 for v in change)):
            excluded.append(dict(joint=joint,reason='prefix_actor_eligibility',**actor));continue
        val=json.loads((parent/'validation'/f'{joint:05d}'/'summary.json').read_text())
        if len(val['cases'])!=3 or val['optimizer_steps']!=0 or not val['model_weights_unchanged']:
            raise ValueError('Invalid validation evidence')
        eligible.append(dict(joint=joint,run=1,checkpoint=str(path.relative_to(ROOT)),checkpoint_sha256=sha(path),
            natural_complete_rate=val['natural_complete_rate'],mean_coverage=val['mean_coverage'],
            mean_coverage_capped95=val['mean_coverage_capped95'],
            penalty_T95_mean=val['penalty_T95_mean'],total_path_m=val['total_path_m'],**actor))
    ranked=sorted(eligible,key=lambda r:(-r['natural_complete_rate'],-r['mean_coverage_capped95'],r['penalty_T95_mean'],r['total_path_m'],r['joint']))
    target=PROJECT/'runs/selection.json'
    if target.exists():raise FileExistsError(target)
    result=dict(status='VAL SELECTED' if ranked else 'NO ELIGIBLE CHECKPOINT / NO-GO',
        selected=ranked[0] if ranked else None,eligible=ranked,excluded=excluded,formally_frozen=False,
        test_rollouts_before_selection=0,parent_joint=summary['actual_joint_decisions'],
        selection_rule='actor eligibility before fixed VAL lexicographic ranking')
    dump(target,result);print(json.dumps(result,indent=2))


if __name__=='__main__':run()
