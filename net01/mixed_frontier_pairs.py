"""Proposed snapshot-only mixed-kind conflicts with original participation guard."""
import math
import json
import os
from pathlib import Path
import time

VERSION='shared-endpoint-mixed-kind-pair-k-preserving-v1'
CONTRACT_FILE='config/NAVIGATION_MIXED_FRONTIER_PAIR_V1.json'

def load_contract(revision):
    contract=json.loads((Path(__file__).resolve().parent/CONTRACT_FILE).read_text())
    if revision!=VERSION or contract['revision']!=VERSION or contract['cell_resolution_m']!=.05:
        raise ValueError('Unknown mixed-frontier pair coordination revision')
    return contract

def adapt_observation(observation):
    from multi_robot_exploration.allocation import frozen
    from multi_robot_exploration.joint import _suffix_work
    if observation['halted'] or not observation['candidates']:
        return observation,dict(scope='No newconstraint afterhalt/withoutcandidates')
    grid=observation['map']
    if grid['resolution']!=.05:raise ValueError('This proposal requires original .05 sharedlattice')
    rows={r['id']:i for i,r in enumerate(observation['robots'])}
    def eligible(index,candidate):
        row=rows[candidate['robot']]
        return observation['robots'][row]['state']=='idle' and observation['action_mask'][row][index]
    def cell(candidate):
        return tuple(math.floor((candidate['shared_frontier_position'][i]-grid['origin'][i])/grid['resolution']) for i in (0,1))
    candidates=observation['candidates'];proposed=set()
    for i,direct in enumerate(candidates):
        if direct['kind']!='frontier' or not eligible(i,direct):continue
        for j,approach in enumerate(candidates):
            if (approach['kind']=='approach' and direct['robot']!=approach['robot']
                    and eligible(j,approach) and cell(direct)==cell(approach)
                    and direct['path_cost_estimate_m'] < approach['path_cost_estimate_m']+approach['remaining_shared_path_m']):
                proposed.add(tuple(sorted((i,j))))
    baseline=_suffix_work(observation,0,());conflicts=set(map(tuple,observation['candidate_conflicts']));added=[];skipped=[]
    for pair in sorted(proposed-conflicts):
        trial=dict(observation,candidate_conflicts=tuple(sorted(conflicts|{pair})))
        work=_suffix_work(trial,0,())
        if work>=baseline:conflicts.add(pair);added.append(pair)
        else:skipped.append(dict(pair=pair,trial_maximum_new_tasks=work))
    return frozen(dict(observation,candidate_conflicts=tuple(sorted(conflicts)))),dict(
        original_maximum_new_tasks=baseline,added_pairs=added,skipped_participation_drop=skipped,
        scope='Originalsame-snapshot legalkinds/estimatedcosts only. No lease, no deadlinefilter, no candidate/value/PPO encoding changes; not a strict route/coverage Pareto proof.')


def install_mixed_frontier_pairs(node, contract):
    if node.allocator.candidate_mode!='rl04_approach_v2':
        raise ValueError('Mixed frontier pairs require original approach-v2 metadata')
    original=node.allocator.get_observation
    state=dict(contract=dict(contract),PID=os.getpid(),events=[],finished=False)
    directory=Path(node.events.name).parent
    def observation(*args,**kwargs):
        with node.lock:
            before=original(*args,**kwargs)
            after,detail=adapt_observation(before)
            state['events'].append(dict(monotonic_ns=time.monotonic_ns(),decision_id=before['decision_id'],map_version=before['map_version'],**detail))
            return after
    def finish_recording():
        if state['finished']:return
        state['finished']=True
        with (directory/'mixed-frontier-pairs.json').open('x') as stream:
            json.dump(state,stream,indent=2)
            stream.write('\n')
    node.allocator.get_observation=observation
    node._mixed_frontier_pair_state=state
    node._finish_mixed_frontier_pair_recording=finish_recording
    return state
