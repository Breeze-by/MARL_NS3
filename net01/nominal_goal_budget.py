"""Single proposed optimistic nominal-goal budget; original joint guards work."""
import math
import json
import os
from pathlib import Path
import time

VERSION='nominal-goal-budget-age-tolerance-credit-v1'
CONTRACT_FILE='config/NAVIGATION_NOMINAL_GOAL_BUDGET_V1.json'

def load_contract(revision):
    contract=json.loads((Path(__file__).resolve().parent/CONTRACT_FILE).read_text())
    if revision!=VERSION or contract['revision']!=VERSION or (contract['vmax_m_per_sim_s'],contract['smac_tolerance_m'],contract['xy_tolerance_m'])!=(.26,.5,.25):
        raise ValueError('Unknown nominal goal budget revision')
    return contract

def adapt_observation(observation, planned_sim_ns, permission_end_ns, vmax, smac_tolerance, xy_tolerance):
    from multi_robot_exploration.allocation import frozen
    from multi_robot_exploration.joint import _suffix_work
    if observation['halted']:
        return observation,dict(scope='No allocation afteroriginalhalt')
    baseline=_suffix_work(observation,0,());current=observation;details=[]
    planned=planned_sim_ns/1e9;remaining=(permission_end_ns-planned_sim_ns)/1e9
    for row,robot in enumerate(observation['robots']):
        if robot['state']!='idle':continue
        legal=[i for i,bit in enumerate(observation['action_mask'][row]) if bit]
        if not legal:continue
        age=max(0.,planned-robot['pose_stamp'])
        allowance=vmax*(remaining+age)+smac_tolerance+xy_tolerance
        distances={i:math.dist(robot['pose'][:2],observation['candidates'][i]['position']) for i in legal}
        inside=[i for i in legal if distances[i]<=allowance]
        outside=[i for i in legal if distances[i]>allowance]
        detail=dict(row=row,robot=robot['id'],planned_sim_ns=planned_sim_ns,permission_end_ns=permission_end_ns,remaining_slot_s=remaining,pose_stamp=robot['pose_stamp'],pose_age_credit_s=age,nominal_distance_allowance_m=allowance,original_legal_distances_m=distances,inside_candidates=inside,outside_candidates=outside)
        if not inside:detail['outcome']='all_far_original_unchanged'
        elif not outside:detail['outcome']='all_legal_inside_unchanged'
        else:
            masks=[list(mask) for mask in current['action_mask']]
            for i in outside:masks[row][i]=False
            trial=dict(current,action_mask=tuple(tuple(m) for m in masks),valid_counts=tuple(sum(m) for m in masks),wait_mask=tuple(r['state']=='idle' and not current['halted'] and not any(m) for r,m in zip(current['robots'],masks)))
            work=_suffix_work(trial,0,());detail['trial_maximum_new_tasks']=work
            if work>=baseline:current=trial;detail['outcome']='filter_accepted_K_preserved'
            else:detail['outcome']='filter_skipped_K_drop'
        details.append(detail)
    return frozen(current),dict(original_maximum_new_tasks=baseline,final_maximum_new_tasks=_suffix_work(current,0,()),rows=details,scope='Only same-row originallegality; receivedpose agecredit and originalconfiguredtolerances make a nominaloptimisticbudget, not physical certificate. No shared_remaining, activecancel or changed candidate/701 numerical values.')


def install_nominal_goal_budget(node, contract, profile):
    if (node.allocator.candidate_mode!=contract['candidate_mode']
            or profile['id']!=contract['execution_profile']
            or profile['startup_contract']['id']!=contract['startup_contract_id']
            or profile['attempt_entry_barrier']['id']!='physical-boundary-attempt-enter-v1'):
        raise ValueError('Nominal budget requires original fixed-slot physicalboundary profile')
    original=node.allocator.get_observation
    state=dict(contract=dict(contract),PID=os.getpid(),events=[],finished=False)
    directory=Path(node.events.name).parent
    def observation(*args,**kwargs):
        with node.lock:
            # consumer installs this gate after HQ construction. Resolve only
            # inside the original current decision callback, never node.now().
            gate=node._fixed_startup_gate
            attempt=gate.rows[-1]
            if (gate.profile!=contract['execution_profile']
                    or gate.contract['id']!=contract['startup_contract_id']
                    or gate.contract['decision_permission_end_ns']!=contract['permission_end_ns']
                    or attempt['kind']!='decision_attempt' or not attempt['attempted']
                    or 'attempt_enter_ACK_sent_monotonic_ns' not in attempt
                    or 'callback_return_monotonic_ns' in attempt):
                raise ValueError('Nominal budget requires current in-progress original attempt entry')
            before=original(*args,**kwargs)
            after,detail=adapt_observation(before,attempt['planned_sim_ns'],gate.contract['decision_permission_end_ns'],contract['vmax_m_per_sim_s'],contract['smac_tolerance_m'],contract['xy_tolerance_m'])
            state['events'].append(dict(monotonic_ns=time.monotonic_ns(),decision_id=before['decision_id'],map_version=before['map_version'],planned_sim_ns=attempt['planned_sim_ns'],permission_end_ns=gate.contract['decision_permission_end_ns'],attempt_enter_ACK_sent_monotonic_ns=attempt['attempt_enter_ACK_sent_monotonic_ns'],**detail))
            return after
    def finish_recording():
        if state['finished']:return
        state['finished']=True
        with (directory/'nominal-goal-budget.json').open('x') as stream:
            json.dump(state,stream,indent=2)
            stream.write('\n')
    node.allocator.get_observation=observation
    node._nominal_goal_budget_state=state
    node._finish_nominal_goal_budget_recording=finish_recording
    return state
