"""Find actual changed greedy behavior using only existing matched VAL records."""
import json
import pickle
import numpy as np
from maps import PROJECT, dump


def compare():
    old = PROJECT/'evidence/p2-diagnosis-01'
    run = PROJECT/'runs/formal-01'
    results = []
    for steps in (1024, 2048, 3072, 4096):
        for serial, seed in enumerate((2101, 2102, 2103)):
            name = f'central_hub_chambers-{seed}'
            old_case = next(p for p in old.iterdir() if p.is_dir() and p.name.endswith(f'{name}-201'))
            new_case = run/'validation'/f'{steps:05d}'/f'{serial:02d}-{name}-201'
            with (old_case/'records.pkl').open('rb') as stream:
                before = pickle.load(stream)
            with (new_case/'records.pkl').open('rb') as stream:
                after = pickle.load(stream)
            result = dict(after_joint_decisions=steps, map=name, seed=201, compared_steps=0,
                before_episode_joint=len(before), after_episode_joint=len(after), first_action_divergence=None,
                input_mismatch_before_any_action_divergence=None)
            for decision, (a, b) in enumerate(zip(before, after), 1):
                if not np.array_equal(a['inputs'], b['inputs']):
                    result['input_mismatch_before_any_action_divergence'] = dict(decision=decision,
                        max_abs_difference=float(np.max(np.abs(a['inputs']-b['inputs']))))
                    break
                result['compared_steps'] += 1
                old_action, new_action = a['action'].choices, b['action'].choices
                if old_action != new_action:
                    first = next(i for i in range(3) if old_action[i] != new_action[i])
                    same_mask = np.array_equal(a['masks'][first], b['masks'][first])
                    result['first_action_divergence'] = dict(decision=decision, first_changed_head=first,
                        old_action=old_action, trained_action=new_action,
                        encoded_input_byte_equal=True, relevant_conditional_mask_equal=bool(same_mask),
                        legal_choices=int(a['masks'][first].sum()),
                        raw_argmax_changed_with_same_input_and_mask=bool(same_mask and a['masks'][first].sum() > 1))
                    break
                if not np.array_equal(a['masks'], b['masks']):
                    raise ValueError('Matched greedy action but different joint masks before divergence')
            results.append(result)
    proven = [r for r in results if r['first_action_divergence'] and
              r['first_action_divergence']['raw_argmax_changed_with_same_input_and_mask']]
    result = dict(status='EXISTING VAL BEHAVIOR AUDIT', comparisons=results,
        actual_changed_greedy_comparisons=len(proven),
        changed_heads=sorted({r['first_action_divergence']['first_changed_head'] for r in proven}),
        initialization='run1 exact weights-only warm start equals P2 old model; run2 not used as a false matched initial',
        nn_forward=0, env_reset=0, env_step=0, optimizer_step=0,
        new_evaluation_episodes=0, does_not_prove_generalization_or_learned_collaboration=True)
    dump(PROJECT/'evidence/val-behavior-change.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'comparisons'}, indent=2))


if __name__ == '__main__':
    compare()
