"""Offline audit of closed real decisions. Never import ROS or an environment."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'workspace/src/multi_robot_exploration'))
from multi_robot_exploration.ppo import ActorCritic, load_checkpoint
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.joint import (
    slot_mask, _base_slot_mask, slot_to_choice, choice_to_slot, JointTraditionalPolicy)
from multi_robot_exploration import frontier


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def table(name, rows):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def snapshots():
    """One original-journal pass; cache only exact actual inference observations."""
    path = OUT / 'snapshots.jsonl'
    if path.exists():
        return [json.loads(line) for line in path.read_text().splitlines()]
    result, manifest = [], []
    for cachepath in sorted((ROOT / 'net01e/followup04/event-cache').glob('corr*.json')):
        cache = json.loads(cachepath.read_text())
        case = cache['case']
        lookup = {x['decision_id']: x for x in cache['inferences']}
        journal = ROOT / f'net01e/followup04/gz-runs/{case}/controller/allocation-events.jsonl'
        events, joint, binding = {}, {}, None
        with journal.open() as f:
            for line_number, line in enumerate(f, 1):
                e = json.loads(line)
                if e['kind'] == 'rl_checkpoint_bound':
                    binding = e
                if e['kind'] == 'rl_joint_action':
                    joint[e['decision_id']] = e
                if e['kind'] == 'rl_real_inference':
                    cached = lookup[e['decision_id']]
                    assert line_number == cached['source_line']
                    assert e['choices'] == cached['choices'] == e['raw_choices']
                    events[e['decision_id']] = e
        assert len(events) == len(lookup) == len(joint)
        manifest.append(dict(case=case, arm=cache['arm'], pair=cache['pair'],
                             journal=str(journal.relative_to(ROOT)),
                             cache=str(cachepath.relative_to(ROOT)),
                             inferences=len(events), goals=len(cache['goals']), binding=binding))
        for did, event in events.items():
            assert not joint[did]['rejected'] and joint[did]['choices'] == event['choices']
            npz = Path(event['input_npz'].replace('/mnt/', ''))
            assert (ROOT / npz).is_file()
            result.append(dict(case=case, arm=cache['arm'], pair=cache['pair'],
                source_line=lookup[did]['source_line'], decision_id=did, sim=event['sim'],
                input_npz=str(npz), observation=event['observed_state_and_candidates'],
                choices=event['choices'], original_conditional_masks=event['original_conditional_masks'],
                actual_conditional_masks=event['actual_conditional_masks'],
                conditional_options=event['conditional_options'], joint_action=joint[did]))
    with path.open('x') as f:
        for row in result:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
    dump('DATA_COVERAGE.json', manifest)
    return result


def legal_leaves(obs, prefix=()):
    if len(prefix) == 3:
        return [prefix]
    return [leaf for slot in np.flatnonzero(slot_mask(obs, len(prefix), prefix))
            for leaf in legal_leaves(obs, (*prefix, slot_to_choice(slot)))]


def select_logits(obs, logits=None, rng=None):
    prefix, masks = [], []
    for row in range(3):
        mask = slot_mask(obs, row, prefix)
        legal = np.flatnonzero(mask)
        slot = int(rng.choice(legal)) if rng is not None else (
            int(legal[0]) if logits is None else int(np.where(mask, logits[row], -np.inf).argmax()))
        prefix.append(slot_to_choice(slot))
        masks.append(mask.tolist())
    return prefix, masks


def raw_groups(obs):
    """Same pre-reachability grouping as Allocator.get_observation, not all legal goals."""
    m = obs['map']
    h, w = m['cells'].shape
    groups_by_robot = []
    for r in obs['robots']:
        col = math.floor((r['pose'][0] - m['origin'][0]) / m['resolution'])
        row = math.floor((r['pose'][1] - m['origin'][1]) / m['resolution'])
        if not (0 <= row < h and 0 <= col < w):
            groups_by_robot.append(dict(groups_all=0, groups_min3=0, frontier_cells=0))
            continue
        data = frontier.costmap(m['cells'], w, h, m['resolution'])
        data[row, col] = 0
        data[data > 5] = 1
        _, groups = frontier.assign_groups(frontier.frontierB(data))
        groups_by_robot.append(dict(groups_all=len(groups),
            groups_min3=sum(len(cells) > 2 for cells in groups.values()),
            frontier_cells=sum(len(cells) for cells in groups.values())))
    return groups_by_robot


def main():
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    rows = snapshots()
    ledger = Ledger(OUT / 'inference-ledger.jsonl', 'policy-audit-offline-replay')
    model = ActorCritic(ledger)
    checkpoint = ROOT / 'policy/checkpoint-00512.pt'
    metadata = load_checkpoint(checkpoint, model, restore_rng=False)
    model.eval()
    captured = []
    hook = model.register_forward_hook(lambda _, __, output: captured.append(
        tuple(v.detach().numpy().copy() for v in output)))
    checkpoints = json.loads((OUT / 'DATA_COVERAGE.json').read_text())
    actual_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert all(c['binding']['checkpoint_sha256'] == actual_sha for c in checkpoints)
    counters, by_case, by_robot = Counter(), defaultdict(Counter), defaultdict(Counter)
    decisions, robot_rows, goal_rows, comparisons = [], [], [], []
    replay_errors = []
    max_errors = Counter()
    rng = np.random.default_rng(2026111201)
    for number, record in enumerate(rows, 1):
        case, did = record['case'], record['decision_id']
        with np.load(ROOT / record['input_npz'], allow_pickle=False) as n:
            obs = record['observation']
            obs['map']['cells'] = n['received_shared_cells'].copy()
            assert np.array_equal(obs['map']['origin'], n['received_origin'])
            assert obs['map']['resolution'] == float(n['received_resolution'])
            actual = model.act(obs, deterministic=True)
            logits, value = captured.pop()
            facts = dict(encoded_equal=np.array_equal(actual['inputs'], n['encoded_inputs']),
                logits_match=np.allclose(logits, n['raw_logits'], rtol=1e-6, atol=1e-6),
                value_match=np.allclose(value, n['raw_value'], rtol=1e-6, atol=1e-6),
                masks_equal=np.array_equal(actual['masks'], n['conditional_masks']),
                journal_masks_equal=np.array_equal(actual['masks'], record['actual_conditional_masks']),
                slots_equal=np.array_equal(actual['slots'], n['slots']),
                choices_equal=list(actual['action'].choices) == record['choices'])
            max_errors['logits_abs'] = max(max_errors['logits_abs'], float(np.max(np.abs(logits-n['raw_logits']))))
            max_errors['value_abs'] = max(max_errors['value_abs'], float(np.max(np.abs(value-n['raw_value']))))
            if not all(facts.values()):
                replay_errors.append(dict(case=case, decision_id=did, checks={k:bool(v) for k,v in facts.items()}))
                # Count facts, but do not manufacture counterfactual input after failed replay.
                continue
            leaves = legal_leaves(obs)
            ppo = list(actual['action'].choices)
            assert tuple(ppo) in leaves
            masks = actual['masks']
            base_masks = np.stack([_base_slot_mask(obs, i, ppo[:i]) for i in range(3)])
            assert np.array_equal(base_masks, record['original_conditional_masks'])
            assert list(masks.sum(axis=1)) == record['conditional_options']
            raw = raw_groups(obs)
            cf = {'traditional': list(JointTraditionalPolicy().select(obs).choices)}
            cf['fixed_order_zero_logits'], zero_masks = select_logits(obs)
            cf['random_seed2026111201'], random_masks = select_logits(obs, rng=rng)
            for name, choices in cf.items():
                assert tuple(choices) in leaves, (case, did, name, choices)
            counts = Counter()
            for i, robot in enumerate(obs['robots']):
                keep, wait = ppo[i] == -1, ppo[i] == -2
                options = int(masks[i].sum())
                label = ('busy_KEEP' if keep else 'no_work_WAIT' if wait else
                         'unique_goal' if options == 1 else 'multi_goal')
                counts[label] += 1
                for c in (counters, by_case[case], by_robot[robot['id']]):
                    c[label] += 1
                    c['robot_rows'] += 1
                    c['idle_rows'] += not keep
                    c['new_goals'] += ppo[i] >= 0
                alternatives = sorted({leaf[i] for leaf in leaves})
                rr = dict(case=case, arm=record['arm'], decision_id=did, robot=robot['id'],
                    sim=record['sim'], state=robot['state'], choice=ppo[i], category=label,
                    raw_groups_all=raw[i]['groups_all'], raw_groups_min3=raw[i]['groups_min3'],
                    retained_candidates_owner=sum(c['robot']==robot['id'] for c in obs['candidates']),
                    single_robot_legal=sum(obs['action_mask'][i]),
                    prefix_legal_before_max_participation=int(base_masks[i, :15].sum()),
                    actual_conditional_options=options,
                    max_participation_removed=int(base_masks[i].sum()-options),
                    global_joint_alternative_count=len(alternatives),
                    global_joint_alternatives=json.dumps(alternatives),
                    **{name+'_choice': action[i] for name, action in cf.items()})
                robot_rows.append(rr)
                if ppo[i] >= 0:
                    candidate = obs['candidates'][ppo[i]]
                    goal_rows.append(dict(rr, candidate_position=json.dumps(candidate['position']),
                        traditional_score=candidate['traditional_score']))
            for c in (counters, by_case[case]):
                c['joint_decisions'] += 1
                c['unique_joint'] += len(leaves)==1
                c['multi_joint'] += len(leaves)>1
                c['joint_with_new_goal'] += bool(counts['unique_goal']+counts['multi_goal'])
                c['joint_with_multi_goal'] += bool(counts['multi_goal'])
            decisions.append(dict(case=case, arm=record['arm'], decision_id=did, sim=record['sim'],
                retained_candidate_total=len(obs['candidates']), joint_legal_leaves=len(leaves),
                **counts, choices=json.dumps(ppo),
                options=json.dumps(masks.sum(axis=1).tolist()),
                base_options=json.dumps(base_masks.sum(axis=1).tolist())))
            comparisons.append(dict(case=case, decision_id=did, ppo=ppo,
                joint_legal_leaves=len(leaves), ppo_new_goal_rows=[i for i,c in enumerate(ppo) if c>=0],
                ppo_multi_rows=[i for i,m in enumerate(masks) if m.sum()>1],
                counterfactuals=cf, zero_masks=zero_masks, random_masks=random_masks,
                legal_joint_actions=[list(l) for l in leaves]))
            obs['map'].pop('cells')
        if number % 35 == 0 or number == len(rows):
            print(f'closed-observation replay {number}/{len(rows)}', flush=True)
    hook.remove()
    dump('REPLAY.json', dict(decisions=len(rows), passed=len(rows)-len(replay_errors),
        errors=replay_errors, max_absolute_error=dict(max_errors),
        checkpoint=str(checkpoint.relative_to(ROOT)), checkpoint_sha256=actual_sha,
        metadata=metadata, torch=torch.__version__, numpy=np.__version__,
        mode='CPU one thread eval/no_grad; 0 optimizer; no ROS/Gazebo imports'))
    if replay_errors:
        raise RuntimeError('Real replay mismatch; no unqualified comparison claim. See REPLAY.json')
    # Every actual new goal must be the unchanged chosen candidate, with exact token/UUID provenance.
    actual_goal_lookup = {(g['case'],g['decision_id'],g['robot']):g for g in goal_rows}
    goal_chain = []
    for cp in checkpoints:
        cache = json.loads((ROOT / cp['cache']).read_text())
        for goal in cache['goals']:
            reserve, request = goal['reservation']['event'], goal['request']['event']
            key=(cp['case'],reserve['decision_id'],goal['robot'])
            chosen=actual_goal_lookup.pop(key)
            position=json.loads(chosen['candidate_position'])
            assert position == reserve['target'] == request['merge_map_target']
            assert reserve['token'] == request['token'] == goal['token']
            assert request['request_uuid'] == goal['UUID']
            goal_chain.append(dict(case=cp['case'],decision_id=reserve['decision_id'],
                robot=goal['robot'],token=goal['token'],uuid=goal['UUID'],
                candidate_choice=chosen['choice'],category=chosen['category'],
                merge_map_target=position,actual_goal_frame=request['actual_goal_frame'],
                actual_goal_position=request['actual_goal_position'],
                request_source_line=goal['request']['source_line'],unchanged_shared_goal=True))
    assert not actual_goal_lookup
    comparison_summary={}
    for name in comparisons[0]['counterfactuals']:
        c=Counter()
        for r in comparisons:
            alt=r['counterfactuals'][name]
            c['joint_decisions']+=1
            c['joint_different']+=alt!=r['ppo']
            c['multi_joint_decisions']+=r['joint_legal_leaves']>1
            c['multi_joint_different']+=(alt!=r['ppo'] and r['joint_legal_leaves']>1)
            for i in r['ppo_new_goal_rows']:
                c['actual_new_goals']+=1
                c['actual_new_goal_different']+=alt[i]!=r['ppo'][i]
            for i in r['ppo_multi_rows']:
                c['actual_multi_rows']+=1
                c['actual_multi_row_different']+=alt[i]!=r['ppo'][i]
        comparison_summary[name]=dict(c)
    dump('SUMMARY.json',dict(total=dict(counters),by_case={k:dict(v) for k,v in by_case.items()},
        by_robot={k:dict(v) for k,v in by_robot.items()},comparison=comparison_summary,
        random_scope='one fixed-seed sequential uniform sample per frozen observation; not performance expectation',
        frozen_observation_scope='PPO-generated state distribution; no counterfactual rollout/return/coverage'))
    table('DECISIONS.csv', [dict({k:0 for k in ('busy_KEEP','no_work_WAIT','unique_goal','multi_goal')},**r) for r in decisions])
    table('ROBOT_ROWS.csv',robot_rows)
    table('NEW_GOALS.csv',goal_rows)
    dump('GOAL_CHAIN.json',goal_chain)
    dump('COUNTERFACTUAL_ACTIONS.json',comparisons)
    print(json.dumps(dict(counters),ensure_ascii=False), flush=True)


if __name__=='__main__':
    main()
