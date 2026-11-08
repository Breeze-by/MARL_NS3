"""Saved36episode three-arm paired analysis; no inference or environment access."""
from collections import Counter,defaultdict
import json
import numpy as np
from common import PROJECT,dump,configuration


def describe(values):
    observed=[v for v in values if v is not None]
    return dict(mean=float(np.mean(observed)) if observed else None,
        median=float(np.median(observed)) if observed else None,available=len(observed),missing=len(values)-len(observed))


def run():
    root=PROJECT/'runs/test-01';summary=json.loads((root/'summary.json').read_text())
    if summary['status']!='LOCKED TEST COMPLETE' or len(summary['cases'])!=36:
        raise ValueError('All36cases required; do not drop failures')
    pairs=defaultdict(dict);arms=('rl','old_reference','traditional');enriched=[]
    for path in sorted(root.glob('*/summary.json')):
        row=json.loads(path.read_text())
        intents=[json.loads(s) for s in (path.parent/'intents.jsonl').read_text().splitlines()]
        decisions=[json.loads(s) for s in (path.parent/'decisions.jsonl').read_text().splitlines()]
        if len(intents)!=len(decisions) or len(intents)!=row['actual_joint']:raise ValueError('Unfinished transition')
        violations=0
        for intent,decision in zip(intents,decisions):
            for event in decision['actual_events']:
                if event['kind']!='accepted':continue
                index=('tb1','tb2','tb3').index(event['robot']);choice=intent['action'][index]
                candidates=intent['observation']['candidates']
                if not 0<=choice<len(candidates):violations+=1;continue
                candidate=candidates[choice]
                violations+=not(candidate['valid'] and candidate['local_map_valid'] and
                    candidate['robot']==event['robot'] and intent['masks'][index][choice] and
                    np.allclose(candidate['position'],event['target'],atol=1e-10))
        values=dict(complete=float(row['natural_complete']),coverage=row['coverage'],
            actual_T90=row['coverage_times'].get('0.9'),actual_T95=row['coverage_times'].get('0.95'),
            penalty_T95=row['coverage_times'].get('0.95',500.),total_path_m=sum(row['paths_m'].values()),
            participation=float(row['all_robot_participation']),minimum_pair_m=row['minimum_pair_m'],
            rejected_actions=row['rejected_robot_actions'],accepted_goals=sum(row['accepted'].values()),
            succeeded_goals=row['navigation_terminals'].get('succeeded',0),aborted_goals=row['navigation_terminals'].get('aborted',0),
            gate_violations=int(violations),actual_joint=row['actual_joint'],
            conditional_idle_seconds=sum(row['conditional_idle_opportunity_seconds'].values()))
        pairs[(row['map'],row['seed'])][row['policy']]=values
        enriched.append(dict(map=row['map'],family=row['family'],seed=row['seed'],arm=row['policy'],
            end_reason=row['end_reason'],nonforced_per_head=row['nonforced_per_head'],
            paths_m=row['paths_m'],metrics=values,stop_verified=row['stop_verified_kinematic']))
    if len(pairs)!=12 or any(set(p)!=set(arms) for p in pairs.values()):raise ValueError('Missing paired arms')
    descriptive={arm:{k:describe([p[arm][k] for p in pairs.values()]) for k in next(iter(pairs.values()))[arm]} for arm in arms}
    counts={arm:dict(episodes=sum(r['arm']==arm for r in enriched),
        natural_complete=sum(r['arm']==arm and r['metrics']['complete']==1 for r in enriched),
        all3participation=sum(r['arm']==arm and r['metrics']['participation']==1 for r in enriched),
        end_reasons=dict(Counter(r['end_reason'] for r in enriched if r['arm']==arm)),
        nonforced_per_head=np.sum([r['nonforced_per_head'] for r in enriched if r['arm']==arm],axis=0).tolist()) for arm in arms}
    comparisons={};config=configuration()
    primary=('complete','coverage','penalty_T95','total_path_m','participation')
    for reference in ('old_reference','traditional'):
        differences={key:{k:p['rl'][k]-p[reference][k] for k in primary} for key,p in pairs.items()}
        map_rows=[]
        for name in sorted({key[0] for key in pairs}):
            group=[v for (m,s),v in differences.items() if m==name]
            family=next(r['family'] for r in enriched if r['map']==name)
            map_rows.append(dict(map=name,family=family,**{k:float(np.mean([r[k] for r in group])) for k in primary}))
        rng=np.random.default_rng(config['bootstrap_seed']);boot=defaultdict(list)
        for _ in range(config['bootstrap_replicates']):
            sample=[]
            for family in sorted({r['family'] for r in map_rows}):
                group=[r for r in map_rows if r['family']==family]
                sample.extend(group[i] for i in rng.integers(0,len(group),len(group)))
            for key in primary:boot[key].append(float(np.mean([r[key] for r in sample])))
        comparisons['rl_minus_'+reference]={k:dict(mean=float(np.mean([r[k] for r in map_rows])),
            paired_median=float(np.median([r[k] for r in differences.values()])),
            map_cluster_family_stratified_CI95=np.quantile(boot[k],[.025,.975]).tolist()) for k in primary}
    gate=(counts['rl']['natural_complete']>=10 and counts['rl']['all3participation']>=10 and
        not any(r['metrics']['gate_violations'] or not r['stop_verified'] or r['metrics']['minimum_pair_m']<.7-1e-9 for r in enriched)
        and not any(r['metrics']['rejected_actions'] for r in enriched if r['arm']=='rl'))
    result=dict(status='DESCRIPTIVE THREE-ARM ANALYSIS',absolute_rl_gate='PASS' if gate else 'FAIL',
        counts=counts,descriptive=descriptive,comparisons=comparisons,cases=enriched,
        scope='6 new within-public-family geometries;2poses each;not novel structural domains',
        attribution='A-B additional training under the new pipeline;no direct new-vs-old pipeline estimate',
        penalty_T95_nonreach_500sim_not_actual_time=True,bootstrap_seed=config['bootstrap_seed'],
        bootstrap_replicates=config['bootstrap_replicates'],nn_forward=0,env_step=0,optimizer_update=0,formally_frozen=False)
    dump(root/'comparison.json',result);print(json.dumps(dict(counts=counts,comparisons=comparisons,absolute_rl_gate=result['absolute_rl_gate']),indent=2))


if __name__=='__main__':run()
