"""Small explanatory tables from already-replayed observations and original logits."""
from collections import Counter
import json
import numpy as np
from audit import ROOT, OUT, dump

snapshots=[json.loads(line) for line in (OUT/'snapshots.jsonl').read_text().splitlines()]
counterfactuals=json.loads((OUT/'COUNTERFACTUAL_ACTIONS.json').read_text())
wanted={('corr6201-common58-r01-a1-fresh02',1,1),
        ('corr6201-common58-r01-a1-fresh02',3,0),('corr6201-common58-r01-b',7,2)}
examples=[]
ranks_all,ranks_multi=Counter(),Counter()
for record,cf in zip(snapshots,counterfactuals):
    obs=record['observation']
    with np.load(ROOT/record['input_npz'],allow_pickle=False) as n:
        for row,choice in enumerate(record['choices']):
            if choice<0:
                continue
            legal=np.flatnonzero(n['conditional_masks'][row])
            candidates=[obs['candidates'][int(i)] for i in legal]
            score=obs['candidates'][choice]['traditional_score']
            rank=1+sum(c['traditional_score']>score for c in candidates)
            ranks_all[rank]+=1
            if len(legal)>1:
                ranks_multi[rank]+=1
            if (record['case'],record['decision_id'],row) not in wanted:
                continue
            logits=n['raw_logits'][0,row,legal]
            p=np.exp(logits-logits.max());p/=p.sum()
            options=[dict(index=c['index'],position=c['position'],kind=c['kind'],
                traditional_score=c['traditional_score'],path_m=c['path_cost_estimate_m'],
                gain_proxy_m2=c['information_gain_proxy_m2'],logit=float(logit),
                masked_softmax=float(prob),ppo_selected=c['index']==choice)
                for c,logit,prob in zip(candidates,logits,p)]
            examples.append(dict(case=record['case'],decision_id=record['decision_id'],
                robot=obs['robots'][row]['id'],actual_prefix=record['choices'][:row],
                actual_ppo_choice=choice,traditional_rank_of_actual_ppo=rank,
                alternatives=options,counterfactual_choices=cf['counterfactuals'],
                scope='Displayed softmax is descriptive over this actual prefix mask; deployed action is deterministic argmax.'))
distribution=Counter(row['joint_legal_leaves'] for row in counterfactuals)
dump('EXAMPLES_AND_RANKS.json',dict(examples=examples,
    traditional_score_rank_of_actual_ppo=dict(all_new_goals=dict(ranks_all),multi_only=dict(ranks_multi)),
    joint_leaf_count_distribution=dict(distribution),
    rank_scope='1 + count of strictly higher traditional scores within actual PPO-prefix legal mask; tie-aware. Not the full traditional counterfactual prefix.'))
print(json.dumps(dict(examples=examples,ranks_all=dict(ranks_all),ranks_multi=dict(ranks_multi),leaf_distribution=dict(distribution)),ensure_ascii=False,indent=2))
