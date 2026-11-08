"""ROS-free checks over persisted requests, ownership and actual run observations."""
import json


def read_controller_records(directory):
    if directory is None:
        return [], []
    path = directory/'allocation-events.jsonl'
    if not path.exists():
        return [], ['Expected controller request log missing']
    rows, errors = [], []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            errors.append(f'Incomplete/malformed controller log line {number}')
    return rows, errors


def request_closure(rows, statuses, active, authority_stopped, extra_owned=None, log_errors=()):
    errors = list(log_errors)
    requests, replies = {}, {}
    terminal = {r:{goal for goal,status in states if status in (4,5,6)} for r,states in statuses.items()}
    for row in rows:
        kind = row['kind']
        if kind == 'rl_actual_nav2_goal_request':
            uuid = row.get('request_uuid')
            if not uuid:
                errors.append('Dispatched goal has no persisted request UUID')
            elif uuid in requests:
                errors.append('Duplicate dispatch UUID: '+uuid)
            else:
                requests[uuid] = row
        elif kind == 'rl_actual_nav2_goal_response':
            replies[row['request_uuid']] = row
        elif kind == 'rl_actual_nav2_goal_result' and row['raw_status'] in (4,5,6):
            uuid = row.get('request_uuid')
            request = requests.get(uuid)
            if request and request['robot']==row['robot'] and request['token']==row['token']:
                terminal[row['robot']].add(uuid)
    owned = {r:{goal for goal,_ in states} for r,states in statuses.items()}
    for robot, goals in (extra_owned or {}).items():
        owned[robot].update(goals)
    unresolved = []
    for uuid, request in requests.items():
        robot = request['robot']
        reply = replies.get(uuid)
        if reply and (reply['robot']!=robot or reply['token']!=request['token']):
            errors.append('Goal response owner mismatch: '+uuid)
        if reply and reply['accepted'] is False:
            continue
        owned[robot].add(uuid)
        if reply and reply.get('accepted_uuid')!=uuid:
            errors.append('Accepted UUID differs from request: '+uuid)
        if uuid not in terminal[robot]:
            unresolved.append(dict(robot=robot, token=request['token'], uuid=uuid,
                response_received=reply is not None))
    unterminated = {r:sorted(goals-terminal[r]) for r,goals in owned.items()}
    closed = (authority_stopped and not errors and not unresolved
              and not any(unterminated.values()) and not any(active.values()))
    return dict(closed=bool(closed), authority_stopped=bool(authority_stopped),
        requests=len(requests), unresolved_requests=unresolved,
        owned_goals={r:sorted(goals) for r,goals in owned.items()},
        unterminated_UUIDs=unterminated, record_errors=errors)


def engineering_closed_loop(rows, result):
    robots = ('tb1','tb2','tb3')
    requests = {(r['robot'],r['token']):r for r in rows if r['kind']=='rl_actual_nav2_goal_request'}
    responses = {r['request_uuid']:r for r in rows if r['kind']=='rl_actual_nav2_goal_response'}
    native_terminals = {(r['robot'],r['token'],r.get('request_uuid')) for r in rows
                        if r['kind']=='rl_actual_nav2_goal_result' and r['raw_status'] in (4,5,6)}
    reserved, inflight, duplicates, terminals, accepted, inferences = {}, {}, [], [], [], []
    for index, row in enumerate(rows):
        kind = row['kind']
        if kind == 'rl_real_inference':
            inferences.append((index,row))
        elif kind == 'goal_reserved':
            key = (row['robot'],row['token'])
            if row['robot'] in inflight:
                duplicates.append(dict(robot=row['robot'], old_token=inflight[row['robot']], new_token=row['token']))
            inflight[row['robot']] = row['token']
            reserved[key] = (index,row)
        elif kind == 'goal_terminal':
            if inflight.get(row['robot'])==row['token']:
                inflight.pop(row['robot'])
            if (row['robot'],row['token'],row.get('uuid')) in native_terminals:
                terminals.append((index,row))
        elif kind == 'goal_accepted':
            accepted.append((index,row))
    joined, target_errors = [], []
    for index, row in accepted:
        key = (row['robot'],row['token'])
        request = requests.get(key)
        reservation = reserved.get(key)
        response = responses.get(row['uuid'])
        if (not request or not reservation or not response or not response['accepted']
                or request.get('request_uuid')!=row['uuid'] or response.get('accepted_uuid')!=row['uuid']
                or tuple(request['merge_map_target'])!=tuple(reservation[1]['target'])):
            target_errors.append(dict(robot=row['robot'], token=row['token']))
        else:
            joined.append((index,row,reservation))
    witnesses = []
    for terminal_index, old in terminals:
        for accepted_index, new, (reserved_index, reservation) in joined:
            if (new['robot']!=old['robot'] or new['token']<=old['token']
                    or new['uuid']==old['uuid'] or accepted_index<=terminal_index):
                continue
            for inference_index, inference in inferences:
                if (terminal_index<inference_index<reserved_index
                        and inference['decision_id']==reservation['decision_id']):
                    robot = next(r for r in inference['observed_state_and_candidates']['robots'] if r['id']==old['robot'])
                    if robot['state']=='idle' and robot['task_token']==old['token']:
                        witnesses.append(dict(robot=old['robot'], terminal_token=old['token'],
                            terminal_uuid=old['uuid'], terminal_status=old['status'],
                            next_decision_id=inference['decision_id'], next_token=new['token'], next_uuid=new['uuid']))
                        break
    facts = dict(bounded_run=result.get('end_reason')=='simulation_budget' and result.get('error') is None,
        no_hazard=result.get('hazard') is None, observed_stop=bool(result.get('observed_stop')),
        actual_NN_three_choices=bool(inferences) and all(len(r['raw_choices'])==3 for _,r in inferences),
        three_owned_accepted=all(any(r['robot']==robot for _,r,_ in joined) for robot in robots),
        three_feedback=all(result.get('counts',{}).get(r+'/feedback',0)>0 for r in robots),
        three_real_movement=all(result.get('max_displacement',{}).get(r,0)>.10 for r in robots),
        SLAM_and_merge_growth=all(result.get('map_changes',{}).get(r,0)>1 for r in (*robots,'merge_map')),
        terminal_feedback_to_new_owner=bool(witnesses), no_owner_overlap=not duplicates,
        request_reservation_linkage=not target_errors,
        no_rejected_RL_actions=not any(r['kind']=='rl_joint_action' and r['rejected'] for r in rows))
    return dict(engineering_closed_loop_pass=all(facts.values()), facts=facts,
        terminal_to_new_owner_witnesses=witnesses, owner_overlap=duplicates,
        target_link_errors=target_errors, actual_inferences=len(inferences),
        accepted_per_robot={r:sum(row['robot']==r for _,row,_ in joined) for r in robots})
