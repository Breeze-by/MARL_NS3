"""No-Gazebo Step/ACK clock with an explicit fixed common prewarm origin.

Identical ten 1ms iterations/10ms clock sampling as original mock fixture.
No pose, SLAM, driver, policy or business publication.
"""
import argparse
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path, required=True)
    parser.add_argument('--initial-sim-ns',type=int,choices=(47_000_000_000,49_000_000_000),default=49_000_000_000)
    args = parser.parse_args()
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.signals import SignalHandlerOptions
    from rosgraph_msgs.msg import Clock
    from std_srvs.srv import Trigger
    rclpy.init(domain_id=92, signal_handler_options=SignalHandlerOptions.NO)
    node = Node('net01e_MOCK_CLOCK')
    publisher = node.create_publisher(Clock, '/clock', qos_profile_sensor_data)
    value = args.initial_sim_ns; iterations = 0; records = []
    def step(request, response):
        nonlocal value, iterations
        before = value; previous_iterations = iterations
        for _ in range(10):
            value += 1_000_000; iterations += 1
            if value % 10_000_000 == 0:
                message = Clock(); message.clock.sec, message.clock.nanosec = divmod(value, 1_000_000_000)
                publisher.publish(message)
        data = dict(before_ns=before, after_ns=value, before_iterations=previous_iterations,
                    after_iterations=iterations, completed_steps=10)
        response.success = True; response.message = json.dumps(data)
        records.append(dict(monotonic_ns=time.monotonic_ns(), **data))
        return response
    node.create_service(Trigger, '/net01/physics_step', step)
    print('REPLAY_MOCK_CLOCK_READY', flush=True)
    try:
        while not args.stop_file.exists():
            rclpy.spin_once(node, timeout_sec=.001)
    finally:
        node.destroy_node(); rclpy.shutdown()
        args.output.write_text(json.dumps(dict(initial_sim_ns=args.initial_sim_ns,
                                               final_sim_ns=value, records=records)) + '\n')


if __name__ == '__main__':
    main()
