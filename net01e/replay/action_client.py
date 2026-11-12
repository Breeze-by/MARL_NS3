"""Fixed logical Goal inputs, real original ActionClient; responses stay dynamic."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'net01'))
SESSION = 2026110912


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path, required=True)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--normal-done-file', type=Path, required=True)
    args = parser.parse_args()
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from rclpy.serialization import serialize_message
    from rclpy.signals import SignalHandlerOptions
    from unique_identifier_msgs.msg import UUID
    from nav2_msgs.action import NavigateToPose
    from action_wire import ActionWire
    args.directory.mkdir(parents=True, exist_ok=False)
    args.journal.parent.mkdir(parents=True, exist_ok=True)
    rclpy.init(domain_id=91, signal_handler_options=SignalHandlerOptions.NO)
    node = Node('net01e_fixed_logical_client', parameter_overrides=[Parameter('use_sim_time', value=True)])
    clients = {r: ActionClient(node, NavigateToPose, ActionWire.name(r)) for r in (1, 2, 3)}
    inputs = {}; requests = {}; handles = {}; results = {}; feedback = {r: 0 for r in clients}
    cancel = None; done = False; rows = []; error = None
    journal = args.journal.open('x', buffering=1)
    def record(kind, **fields):
        row = dict(kind=kind, monotonic_ns=time.monotonic_ns(), sim_ns=node.get_clock().now().nanoseconds, **fields)
        rows.append(row); journal.write(json.dumps(row) + '\n')
    for robot in clients:
        goal = NavigateToPose.Goal(); goal.pose.header.frame_id = 'map'; goal.pose.header.stamp.sec = 52
        goal.pose.pose.position.x = robot + .125; goal.pose.pose.position.y = -2.75
        goal.pose.pose.orientation.z = .6; goal.pose.pose.orientation.w = .8
        goal.behavior_tree = 'NET01E controlled fixture; no Nav2 tree execution'
        uuid = UUID(uuid=list(SESSION.to_bytes(8, 'big') + bytes([robot]) + bytes(7)))
        inputs[robot] = dict(goal=goal, uuid=uuid)
        record('PLANNED_LOGICAL_GOAL', robot=robot, due_sim_ns=52_000_000_000,
               uuid=bytes(uuid.uuid).hex(), Goal_CDR=serialize_message(goal).hex())
    record('PLANNED_LOGICAL_CANCEL', robot=3, due_sim_ns=55_000_000_000,
           uuid=bytes(inputs[3]['uuid'].uuid).hex())
    (args.directory / 'planned-logical-inputs.json').write_text(json.dumps(rows, indent=2) + '\n')
    begin = time.monotonic()
    try:
        while not args.stop_file.exists():
            if time.monotonic() - begin > 60:
                raise TimeoutError('logical Action client 60wall hard bound')
            rclpy.spin_once(node, timeout_sec=.001)
            now = node.get_clock().now().nanoseconds
            if now >= 52_000_000_000 and not requests:
                if not all(client.server_is_ready() for client in clients.values()):
                    raise RuntimeError('actual Action endpoint not ready at fixed52sim Goal input')
                for robot, client in clients.items():
                    def received(message, robot=robot):
                        if bytes(message.goal_id.uuid) != bytes(inputs[robot]['uuid'].uuid):
                            raise ValueError('foreign feedback UUID')
                        feedback[robot] += 1
                    item = inputs[robot]
                    record('rl_actual_nav2_goal_request', robot=f'tb{robot}', uuid=bytes(item['uuid'].uuid).hex(),
                           Goal_CDR=serialize_message(item['goal']).hex())
                    requests[robot] = client.send_goal_async(item['goal'], goal_uuid=item['uuid'],
                                                             feedback_callback=received)
            for robot, future in requests.items():
                if future.done() and robot not in handles:
                    handle = future.result(); handles[robot] = handle
                    if not handle.accepted or bytes(handle.goal_id.uuid) != bytes(inputs[robot]['uuid'].uuid):
                        raise ValueError('Goal rejected or UUID changed')
                    record('rl_actual_nav2_goal_response', robot=f'tb{robot}', accepted=True,
                           uuid=bytes(handle.goal_id.uuid).hex())
                    results[robot] = handle.get_result_async()
            if now >= 55_000_000_000 and cancel is None:
                if 3 not in handles:
                    raise RuntimeError('tb3 Goal not accepted by fixed55sim Cancel input')
                cancel = handles[3].cancel_goal_async()
                record('LOGICAL_CANCEL_SUBMITTED', robot='tb3', uuid=bytes(inputs[3]['uuid'].uuid).hex(),
                       due_sim_ns=55_000_000_000)
            if results and len(results) == 3 and all(f.done() for f in results.values()) and not done:
                statuses = {r: future.result().status for r, future in results.items()}
                if statuses != {1: 4, 2: 4, 3: 5} or not all(feedback.values()):
                    raise ValueError(f'actual outcomes or feedback differ: {statuses}')
                if cancel is None or not cancel.done():
                    continue
                response = cancel.result()
                if response.return_code != 0 or [bytes(g.goal_id.uuid) for g in response.goals_canceling] != [bytes(inputs[3]['uuid'].uuid)]:
                    raise ValueError('actual Cancel original UUID response differs')
                for robot, status in statuses.items():
                    record('rl_actual_nav2_goal_result', robot=f'tb{robot}', uuid=bytes(inputs[robot]['uuid'].uuid).hex(), status=status)
                args.normal_done_file.write_text(json.dumps(dict(statuses=statuses, feedback=feedback)))
                done = True
    except BaseException as exc:
        error = repr(exc); raise
    finally:
        journal.close()
        (args.directory / 'result.json').write_text(json.dumps(dict(error=error, normal_done=done,
                                                                   records=rows, feedback=feedback), indent=2) + '\n')
        for client in clients.values():
            client.destroy()
        node.destroy_node(); rclpy.shutdown()


if __name__ == '__main__':
    main()
