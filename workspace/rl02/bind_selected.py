"""Bind the actual selected early/final checkpoint without any NN forward."""
import json
import numpy as np
import torch
from maps import ROOT, PROJECT, dump, sha
from train import validate_checkpoint


def bind():
    selection_path = PROJECT/'runs/selection.json'
    selected = json.loads(selection_path.read_text())['selected']
    path = ROOT/selected['checkpoint']
    parent = path.parent
    summary = json.loads((parent/'summary.json').read_text())
    checkpoint = validate_checkpoint(path, summary)
    if sha(path) != selected['checkpoint_sha256']:
        raise ValueError('Selected model hash no longer matches selection')
    initial = torch.load(parent/'initial.pt', map_location='cpu', weights_only=False)
    prefix_steps = checkpoint['metadata']['joint_decisions']
    samples, nonforced = 0, np.zeros(3, dtype=int)
    for batch in sorted(parent.glob('rollout-*.npz')):
        after_joint = int(batch.stem.split('-')[-1])
        if after_joint <= prefix_steps:
            data = np.load(batch)
            samples += len(data['reward'])
            nonforced += (data['masks'].sum(axis=2) > 1).sum(axis=0)
    updates = [json.loads(s) for s in (parent/'updates.jsonl').read_text().splitlines()]
    gradients = np.asarray([r['per_head_actor_weight_gradient'] for r in updates if r['after_joint_decisions'] <= prefix_steps])
    if samples != prefix_steps or len(gradients) != prefix_steps//256*8:
        raise ValueError('Selected prefix training evidence is incomplete')
    actor_delta = (checkpoint['model']['actor.weight']-initial['model']['actor.weight']).reshape(3, 17, -1).norm(dim=(1, 2)).tolist()
    learned = bool((nonforced >= 20).all() and (gradients.max(axis=0) > 0).all() and all(v > 0 for v in actor_delta))
    result = dict(status='SELECTED ARTIFACT BOUND', selection_sha256=sha(selection_path),
        checkpoint=str(path.relative_to(ROOT)), checkpoint_sha256=sha(path),
        actual_checkpoint_joint=prefix_steps, actual_adam_step=prefix_steps//256*8,
        parent_completed_joint=summary['actual_joint_decisions'],
        parent_native_exit=json.loads((parent/'process-exit.json').read_text())['exit_code'],
        actual_prefix_unique_samples=samples, actual_prefix_nonforced_per_head=nonforced.tolist(),
        prefix_per_head_nonzero_gradient_minibatches=(gradients > 0).sum(axis=0).tolist(),
        selected_per_head_actor_weight_change_from_initial=actor_delta,
        selected_prefix_learning_minimum_met=learned,
        encoding=checkpoint['metadata']['encoding'], roi=checkpoint['metadata']['task_roi'],
        hidden=checkpoint['metadata']['config']['hidden'], source_metadata=checkpoint['metadata'],
        nn_forward=0, env_step=0, optimizer_step=0, candidate_formally_frozen=False,
        evaluation_performance_not_inferred=True)
    target = PROJECT/'runs/selected-binding.json'
    if target.exists():
        raise FileExistsError('Selected model binding is already sealed')
    dump(target, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'source_metadata'}, indent=2))


if __name__ == '__main__':
    bind()
