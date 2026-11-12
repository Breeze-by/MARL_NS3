"""Analytic sequential-random, inherited checkpoint and observation sensitivity."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from audit import ROOT, OUT, dump, select_logits
from multi_robot_exploration.ppo import ActorCritic, load_checkpoint
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.joint import slot_mask, choice_to_slot


def main():
    assert json.loads((OUT/'REPLAY.json').read_text())['passed']==212
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    snapshots=[json.loads(line) for line in (OUT/'snapshots.jsonl').read_text().splitlines()]
    cf=json.loads((OUT/'COUNTERFACTUAL_ACTIONS.json').read_text())
    ledger=Ledger(OUT/'sensitivity-ledger.jsonl','policy-audit-offline-inherited-and-zero-input')
    initial=Path('/home/zhuyulab/ns3-workspace/rl-04/runs/formal-01/initial.pt')
    selection=json.loads((initial.parent.parent/'selection.json').read_text())
    initial_binding=next(e for e in selection['eligible'] if e['joint']==0)
    initial_sha=hashlib.sha256(initial.read_bytes()).hexdigest()
    assert initial_sha==initial_binding['checkpoint_sha256']
    previous=ActorCritic(ledger)
    metadata=load_checkpoint(initial,previous,restore_rng=False)
    previous.eval()
    trained=ActorCritic(ledger)
    load_checkpoint(ROOT/'policy/checkpoint-00512.pt',trained,restore_rng=False)
    trained.eval()
    zero_logits=trained(torch.zeros((1,701),dtype=torch.float32))[0][0].numpy()
    delta={}
    for group,prefix in [('actor_head','actor.'),('trunk','trunk.'),('critic','critic.')]:
        values=[(v-previous.state_dict()[k]).flatten() for k,v in trained.state_dict().items() if k.startswith(prefix)]
        vector=torch.cat(values)
        delta[group]=dict(l2=float(vector.norm()),changed_elements=int(torch.count_nonzero(vector)),elements=vector.numel())
    decisions,random_rows=[],[]
    summary=Counter()
    cross_global=Counter({k:0 for k in ('globally_fixed','globally_fixed_new_goal',
        'direct_multi','direct_multi_new_goal','prefix_indirect','prefix_indirect_new_goal')})
    logit_margins=[]
    for record,comparative in zip(snapshots,cf):
        assert (record['case'],record['decision_id'])==(comparative['case'],comparative['decision_id'])
        obs=record['observation']
        with np.load(ROOT/record['input_npz'],allow_pickle=False) as n:
            obs['map']['cells']=n['received_shared_cells'].copy()
            ppo=record['choices']
            initial_record=previous.act(obs,deterministic=True)
            assert np.array_equal(initial_record['inputs'],n['encoded_inputs'])
            inherited=list(initial_record['action'].choices)
            zero,zero_masks=select_logits(obs,logits=zero_logits)
            leaves=comparative['legal_joint_actions']
            assert inherited in leaves and zero in leaves
            summary['joint_decisions']+=1
            summary['initial_joint_different']+=inherited!=ppo
            summary['zero_input_joint_different']+=zero!=ppo
            summary['multi_joint_decisions']+=len(leaves)>1
            leaf_probs=[]
            for leaf in leaves:
                probability=1.
                for row,choice in enumerate(leaf):
                    probability/=int(slot_mask(obs,row,leaf[:row]).sum())
                leaf_probs.append(probability)
            assert math_is_one(sum(leaf_probs))
            p_same=sum(p for leaf,p in zip(leaves,leaf_probs) if leaf==ppo)
            summary['random_expected_joint_different']+=1.-p_same
            new_goal_expected=0.
            for i,choice in enumerate(ppo):
                global_set=sorted({leaf[i] for leaf in leaves})
                direct=int(np.count_nonzero(n['conditional_masks'][i]))
                influence=('direct_multi' if direct>1 else 'prefix_indirect' if len(global_set)>1 else 'globally_fixed')
                cross_global[influence]+=1
                cross_global[influence+'_new_goal']+=choice>=0
                if choice>=0:
                    summary['new_goals']+=1
                    summary['initial_new_goal_different']+=inherited[i]!=choice
                    summary['zero_input_new_goal_different']+=zero[i]!=choice
                    new_goal_expected+=sum(p for leaf,p in zip(leaves,leaf_probs) if leaf[i]!=choice)
                if direct>1:
                    summary['direct_multi_rows']+=1
                    summary['initial_direct_multi_different']+=inherited[i]!=choice
                    summary['zero_input_direct_multi_different']+=zero[i]!=choice
                    legal_logits=n['raw_logits'][0,i,n['conditional_masks'][i]]
                    ordered=np.sort(legal_logits)
                    logit_margins.append(float(ordered[-1]-ordered[-2]))
            summary['random_expected_new_goal_different']+=new_goal_expected
            random_rows.append(dict(case=record['case'],decision_id=record['decision_id'],
                legal_joint_actions=leaves,conditional_uniform_leaf_probabilities=leaf_probs,
                probability_of_actual_PPO_joint=p_same,
                expected_different_actual_new_goals=new_goal_expected))
            decisions.append(dict(case=record['case'],decision_id=record['decision_id'],
                ppo=ppo,inherited_initial=inherited,zero_input_ranking=zero,
                inherited_masks=initial_record['masks'].tolist(),zero_input_masks=zero_masks))
    dump('INITIAL_AND_OBSERVATION_SENSITIVITY.json',dict(summary=dict(summary),
        initial_path=str(initial),initial_sha256=initial_sha,initial_metadata=metadata,
        initial_scope='RL04 pre-additional-PPO checkpoint inherited already-trained RL03 weights; NOT random/untrained',
        parameter_delta_initial_to_selected=delta,
        zero_input_scope='701 zeros only generate a fixed ranking, actual observed candidates/masks remain; not a deployable observation or performance test',
        zero_input_logits=zero_logits.tolist(),rows=decisions))
    dump('ANALYTIC_SEQUENTIAL_RANDOM.json',dict(
        method='uniform per conditional mask, each own prefix recomputed; product reciprocal branching; NOT uniform over joint leaves',
        expected_different_joint_decisions=summary['random_expected_joint_different'],
        expected_different_actual_new_goals=summary['random_expected_new_goal_different'],rows=random_rows))
    robot=list(csv.DictReader((OUT/'ROBOT_ROWS.csv').open()))
    groups=Counter(int(r['actual_conditional_options']) for r in robot if int(r['choice'])>=0)
    dump('CHOICE_LAYERS.json',dict(
        across_all_joint_leaves=dict(cross_global),new_goal_option_distribution=dict(groups),
        maximum_participation_rows_reduced=sum(int(r['max_participation_removed'])>0 for r in robot),
        maximum_participation_goal_rows_reduced=sum(int(r['max_participation_removed'])>0 for r in robot if int(r['choice'])>=0),
        maximum_participation_options_removed=sum(int(r['max_participation_removed']) for r in robot),
        raw_geometric_min3_groups_per_robot_row_range=[min(int(r['raw_groups_min3']) for r in robot),max(int(r['raw_groups_min3']) for r in robot)],
        raw_scope='shared received map geometry only, original frontier functions + robot seed override; not pre-navigation eligible goal reconstruction',
        actual_multi_logit_margin=dict(min=min(logit_margins),median=float(np.median(logit_margins)),max=max(logit_margins)),
        limits='No action agreement or logit margin is a return/coverage advantage estimate.'))
    history_path=ROOT/'evidence/followup-10/FINAL_SIX_RUN_SUMMARY.json'
    history=json.loads(history_path.read_text())
    historical=[]
    for r in history['rows']:
        metric=r['records']['metric']
        historical.append(dict(case=r['case'],arm=r['arm'],runtime_source=r['runtime_source'],
            autonomy_sim=r['autonomy_sim'],T95=metric['thresholds']['0.95']['elapsed_sim_s'],
            T98=metric['thresholds']['0.98']['elapsed_sim_s'],coverage=metric['coverage'],
            stop=r['stop'],three_pause=r['three_pause'],integrity=r['integrity'],
            natural_completion_verified=r['natural_completion_verified']))
    dump('HISTORICAL_COMPARISON.json',dict(source=str(history_path.relative_to(ROOT)),
        scope=history['scope'],rows=historical,
        inference='Historical one pair per exposed geometry; not six new common58-policy comparisons or generalization proof.'))
    legacy=Path('/home/zhuyulab/ns3-workspace/rl-04/runs/test-01/comparison.json')
    old=json.loads(legacy.read_text())
    dump('LEGACY_2D_LEARNING_EVIDENCE.json',dict(source=str(legacy),
        **{k:old[k] for k in ('scope','attribution','counts','descriptive','comparisons','common_success_only',
                             'penalty_T95_nonreach_500sim_not_actual_time','optimizer_update')},
        limits='Historical projected-2D backend; not Gazebo/SLAM/new common58; existing uncertainty copied without new bootstrap.'))
    print(json.dumps(dict(summary),ensure_ascii=False,indent=2))
    print(json.dumps(dict(cross_global),ensure_ascii=False))


def math_is_one(value):
    return abs(value-1.)<1e-12


if __name__=='__main__':
    main()
