"""One preregistered selection, including the unchanged initial-weights reference."""
import json
import numpy as np
import torch
from common import PROJECT, ROOT, dump, sha
from train import validate_checkpoint


def ranking(row):
    return (-row['natural_complete_rate'], -row['all_robot_participation_rate'],
            row['penalty_T95_mean'], row['total_path_m'], row['joint'])


def run():
    parent = PROJECT/'runs/formal-01'
    target = PROJECT/'runs/selection.json'
    if target.exists():
        raise FileExistsError(target)
    summary = json.loads((parent/'summary.json').read_text())
    if json.loads((parent/'process-exit.json').read_text())['exit_code'] != 0:
        raise ValueError('Formal parent did not exit0')
    rollouts = [json.loads(s) for s in (parent/'rollouts.jsonl').read_text().splitlines()]
    updates = [json.loads(s) for s in (parent/'updates.jsonl').read_text().splitlines()]
    initial = torch.load(parent/'initial.pt', map_location='cpu', weights_only=False)['model']['actor.weight']
    eligible, excluded = [], []
    for joint in (0, 512, 1024, 2048):
        path = parent/('initial.pt' if joint == 0 else f'checkpoint-{joint:05d}.pt')
        checkpoint = validate_checkpoint(path, summary)
        if checkpoint['metadata']['config']['observation_contract'] != 'rl04-shared-frontier-approach-v2':
            raise ValueError('Checkpoint contract mismatch')
        actor = dict(additional_joint_decisions=joint, additional_Adam_steps=joint//256*8,
            inherited_reference=(joint == 0), inherited_parent_Adam_steps=64)
        if joint:
            opportunities = np.sum([r['nonforced_per_head'] for r in rollouts if r['after_joint_decisions'] <= joint], axis=0)
            gradients = np.max([r['per_head_actor_weight_gradient'] for r in updates if r['after_joint_decisions'] <= joint], axis=0)
            change = (checkpoint['model']['actor.weight']-initial).reshape(3, 17, -1).norm(dim=(1, 2)).tolist()
            actor.update(nonforced_per_head=opportunities.tolist(), maximum_actor_gradient_per_head=gradients.tolist(),
                         net_actor_weight_change_per_head=change)
            if not (np.all(opportunities >= 20) and np.all(gradients > 0) and all(v > 0 for v in change)):
                excluded.append(dict(joint=joint, reason='prefix_actor_eligibility', **actor))
                continue
        val = json.loads((parent/'validation'/f'{joint:05d}'/'summary.json').read_text())
        if len(val['cases']) != 3 or val['optimizer_steps'] != 0 or not val['model_weights_unchanged']:
            raise ValueError('Invalid validation evidence')
        if val['checkpoint_sha256'] != sha(path):
            raise ValueError('Validation checkpoint binding mismatch')
        eligible.append(dict(joint=joint, run=1, checkpoint=str(path.relative_to(ROOT)), checkpoint_sha256=sha(path),
            natural_complete_rate=val['natural_complete_rate'],
            all_robot_participation_rate=val['all_robot_participation_rate'],
            mean_coverage=val['mean_coverage'], penalty_T95_mean=val['penalty_T95_mean'],
            total_path_m=val['total_path_m'], **actor))
    ranked = sorted(eligible, key=ranking)
    selected = ranked[0]
    result = dict(status='VAL SELECTED', selected=selected, eligible=ranked, excluded=excluded,
        formally_frozen=False, test_rollouts_before_selection=0, parent_joint=summary['actual_joint_decisions'],
        additional_PPO_checkpoint_selected=selected['joint'] > 0,
        test_reference_contract=('rl03_local_v1' if selected['joint'] == 0 else 'rl04_approach_v2'),
        selection_rule='eligible initial or actor-qualified prefix; natural, participation, penalty_T95, path, earliest joint')
    dump(target, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    run()
