"""Exactly one metered selected-model replay of an already-saved VAL input."""
import json
import pickle
import numpy as np
import torch
from torch.distributions import Categorical
from maps import ROOT, PROJECT, dump, sha
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.ppo import ActorCritic, load_checkpoint


def replay():
    output = PROJECT/'evidence/selected-replay-01'
    output.mkdir(parents=True, exist_ok=False)
    selected = json.loads((PROJECT/'runs/selection.json').read_text())['selected']
    binding = json.loads((PROJECT/'runs/selected-binding.json').read_text())
    path = ROOT/selected['checkpoint']
    if sha(path) != selected['checkpoint_sha256'] or binding['checkpoint_sha256'] != selected['checkpoint_sha256']:
        raise ValueError('Selected replay model differs from sealed binding')
    record_path = path.parent/'validation'/f'{selected["joint"]:05d}'/'00-central_hub_chambers-2101-201/records.pkl'
    with record_path.open('rb') as stream:
        original = pickle.load(stream)[0]
    ledger = Ledger(output/'ledger.jsonl', 'selected_saved_val_replay')
    torch.set_num_threads(1)
    model = ActorCritic(ledger, 128)
    load_checkpoint(path, model, restore_rng=False)
    model.eval()
    with torch.no_grad():
        logits, value = model(torch.from_numpy(original['inputs'])[None])
        masks = torch.from_numpy(original['masks'])
        distribution = Categorical(logits=logits[0].masked_fill(~masks, -torch.inf))
        slots = distribution.logits.argmax(dim=-1)
        joint_logprob = float(distribution.log_prob(torch.from_numpy(original['slots'])).sum())
        entropy = float(distribution.entropy().sum())
    value_error = abs(float(value[0])-original['value'])
    logprob_error = abs(joint_logprob-original['logprob'])
    entropy_error = abs(entropy-original['entropy'])
    argmax_same = bool(np.array_equal(slots.numpy(), original['slots']))
    passed = bool(value_error <= 1e-6 and logprob_error <= 1e-6 and entropy_error <= 1e-6 and argmax_same)
    ledger.flush('selected_replay_end', passed=passed)
    result = dict(status='PASS' if passed else 'FAIL', checkpoint_sha256=sha(path),
        actual_checkpoint_joint=selected['joint'], saved_input=str(record_path.relative_to(ROOT)),
        saved_records_sha256=sha(record_path), record_index=0, input_dim=len(original['inputs']),
        expected_value=original['value'], replay_value=float(value[0]), value_abs_error=value_error,
        expected_joint_logprob=original['logprob'], replay_joint_logprob=joint_logprob,
        joint_logprob_abs_error=logprob_error, entropy_abs_error=entropy_error,
        expected_masked_argmax_slots=original['slots'].tolist(), replay_masked_argmax_slots=slots.tolist(),
        argmax_equal=argmax_same, absolute_float_tolerance=1e-6, counts=dict(ledger.counts),
        nn_forward=ledger.counts['policy_forward'], nn_samples=ledger.counts['policy_forward_samples'],
        env_step=0, new_episode=0, optimizer_step=0, policy_formally_frozen=False)
    dump(output/'result.json', result)
    print(json.dumps(result, indent=2))
    if not passed:
        raise RuntimeError('Reloaded selected checkpoint did not reproduce saved VAL outputs')


if __name__ == '__main__':
    replay()
