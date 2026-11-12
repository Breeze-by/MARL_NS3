"""Existing ControlledServer semantics and real local PAUSE endpoints, no motion."""
import argparse
import json
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'net01'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path, required=True)
    args = parser.parse_args()
    import rclpy
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from rclpy.qos import QoSProfile, DurabilityPolicy
    from rclpy.signals import SignalHandlerOptions
    from nav2_msgs.srv import ManageLifecycleNodes
    from std_msgs.msg import String
    from std_srvs.srv import Trigger
    from check_action_wire import ControlledServer
    rclpy.init(domain_id=92, signal_handler_options=SignalHandlerOptions.NO)
    node = Node('net01e_controlled_servers', parameter_overrides=[Parameter('use_sim_time', value=True)])
    servers = {r: ControlledServer(node, r) for r in (1, 2, 3)}
    clients = {r: node.create_client(Trigger, f'/net01/tb{r}/arm') for r in servers}
    arm = {}; status = None; pauses = []
    def state(message):
        nonlocal status
        status = json.loads(message.data)
    node.create_subscription(String, '/net01/gateway_state', state,
                             QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
    def pause(robot, request, response):
        pauses.append(dict(robot=robot, command=request.command, monotonic_ns=time.monotonic_ns()))
        response.success = request.command == ManageLifecycleNodes.Request.PAUSE
        return response
    services = [node.create_service(ManageLifecycleNodes,
        f'/tb{r}/lifecycle_manager_navigation/manage_nodes',
        lambda request, response, robot=r: pause(robot, request, response)) for r in servers]
    begin = time.monotonic()
    try:
        print('COLLECTION_ACTION_SERVERS_READY', flush=True)
        while not args.stop_file.exists():
            if time.monotonic() - begin > 60:
                raise TimeoutError('controlled servers 60wall bound')
            rclpy.spin_once(node, timeout_sec=.001)
            if node.get_clock().now().nanoseconds >= 54_000_000_000:
                for r in (1, 2):
                    servers[r].release.update(servers[r].executing)
            if status:
                for robot, client in clients.items():
                    guard = status['guards'][str(robot)]
                    pending = arm.get(robot)
                    if (not guard['armed'] and guard['reason'] is None and guard['fault'] is None
                            and client.service_is_ready() and (pending is None or pending.done())):
                        arm[robot] = client.call_async(Trigger.Request())
    finally:
        args.output.write_text(json.dumps(dict(pauses=pauses,
            servers={str(r): dict(accepted=s.accepted, cancelled=s.cancelled,
                                   executing=list(s.executing)) for r, s in servers.items()},
            arm={str(r): dict(success=f.result().success, message=f.result().message)
                 if f.done() else None for r, f in arm.items()},
            scope='Original ControlledServer fixture only; no Nav2 or physical movement.')) + '\n')
        for server in servers.values():
            server.close()
        node.destroy_node(); rclpy.shutdown()


if __name__ == '__main__':
    main()
