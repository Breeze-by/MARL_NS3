"""Synthetic log certificates only: no policy, ROS node or physics execution."""
from maps import PROJECT, dump
from execution_evidence import request_closure, engineering_closed_loop


def run():
    output = PROJECT/'evidence/certificate-fixture-01'
    output.mkdir(parents=True, exist_ok=False)
    robots = ('tb1','tb2','tb3')
    empty = {r:set() for r in robots}
    request = dict(kind='rl_actual_nav2_goal_request', robot='tb1', token=1,
                   request_uuid='11'*16, merge_map_target=[1.,1.])
    reply = dict(kind='rl_actual_nav2_goal_response', robot='tb1', token=1,
                 request_uuid='11'*16, accepted=True, accepted_uuid='11'*16)
    cases = []
    for label, rows, expected in (
            ('unseen_pending_request', [request], False),
            ('accepted_without_terminal', [request,reply], False),
            ('explicit_rejection', [request,dict(reply, accepted=False, accepted_uuid=None)], True),
            ('actual_canceled_result', [request,reply,dict(kind='rl_actual_nav2_goal_result',
                robot='tb1', token=1, request_uuid='11'*16, raw_status=5)], True)):
        result = request_closure(rows, empty, empty, True)
        assert result['closed']==expected
        cases.append(dict(case=label, expected=expected, result=result))
    rows = []
    def inference(decision, tokens):
        rows.append(dict(kind='rl_real_inference', decision_id=decision, raw_choices=[0,1,2],
            observed_state_and_candidates=dict(robots=[dict(id=r,state='idle',task_token=t)
                                                       for r,t in zip(robots,tokens)])))
    def assign(robot, token, uuid, decision):
        target = [float(token),float(robots.index(robot))]
        rows.extend([dict(kind='goal_reserved',robot=robot,token=token,target=target,decision_id=decision),
            dict(kind='rl_actual_nav2_goal_request',robot=robot,token=token,request_uuid=uuid,merge_map_target=target),
            dict(kind='rl_actual_nav2_goal_response',robot=robot,token=token,request_uuid=uuid,accepted=True,accepted_uuid=uuid),
            dict(kind='goal_accepted',robot=robot,token=token,uuid=uuid)])
    def finish(robot, token, uuid, status):
        rows.extend([dict(kind='rl_actual_nav2_goal_result',robot=robot,token=token,request_uuid=uuid,raw_status=status),
            dict(kind='goal_terminal',robot=robot,token=token,uuid=uuid,status={4:'succeeded',5:'canceled'}[status])])
    inference(1,[0,0,0])
    for i,r in enumerate(robots):
        assign(r,1,('%02x'%(i+1))*16,1)
    finish('tb1',1,'01'*16,4)
    inference(2,[1,1,1])
    assign('tb1',2,'04'*16,2)
    for i,r in enumerate(robots):
        finish(r,2 if i==0 else 1,('04' if i==0 else '%02x'%(i+1))*16,5)
    observed = dict(end_reason='simulation_budget',error=None,hazard=None,observed_stop=True,
        counts={r+'/feedback':1 for r in robots},max_displacement={r:1. for r in robots},
        map_changes={r:2 for r in (*robots,'merge_map')})
    positive = engineering_closed_loop(rows,observed)
    assert positive['engineering_closed_loop_pass']
    assert request_closure(rows,empty,empty,True)['closed']
    no_new_owner = engineering_closed_loop([r for r in rows if not(r['kind']=='goal_accepted'
        and r['robot']=='tb1' and r['token']==2)],observed)
    assert not no_new_owner['engineering_closed_loop_pass']
    no_real_terminal = engineering_closed_loop([r for r in rows if r['kind']!='rl_actual_nav2_goal_result'],observed)
    assert not no_real_terminal['engineering_closed_loop_pass']
    dump(output/'result.json',dict(status='PASS',request_cases=cases,
        engineering_positive_with_only_one_success=positive,
        missing_new_accepted_owner_rejected=not no_new_owner['engineering_closed_loop_pass'],
        high_level_terminal_without_real_result_rejected=not no_real_terminal['engineering_closed_loop_pass'],
        actual_ros_node_init=0,actual_service_requests=0,nn_forward=0,env_reset=0,env_step=0,
        optimizer_step=0,gazebo_start=0,scope='Controlled fake logs only; no runtime or stopping claim.'))
    print('PASS: unseen pending denied, terminal/response closure checked, actual new owner required; 0 runtime calls.')


if __name__=='__main__':
    run()
