"""One bounded read-only discovery check: require exclusive domains91/92."""
import argparse
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import rclpy
    from rclpy.context import Context
    from rclpy.node import Node
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.signals import SignalHandlerOptions
    rows = []; objects = []
    for domain in (91, 92):
        context = Context(); rclpy.init(context=context, domain_id=domain, signal_handler_options=SignalHandlerOptions.NO)
        name = 'net01e_exclusive_preflight_' + str(domain)
        node = Node(name, context=context); executor = SingleThreadedExecutor(context=context); executor.add_node(node)
        objects.append((domain, name, context, node, executor))
    try:
        until = time.monotonic() + 1
        while time.monotonic() < until:
            for _, _, _, _, executor in objects:
                executor.spin_once(timeout_sec=.005)
        for domain, name, _, node, _ in objects:
            unexpected = [(n, namespace) for n, namespace in node.get_node_names_and_namespaces() if n != name]
            rows.append(dict(domain=domain, unexpected_nodes=unexpected))
        args.output.write_text(json.dumps(dict(rows=rows, pass_exclusive=all(not row['unexpected_nodes'] for row in rows))) + '\n')
        return int(any(row['unexpected_nodes'] for row in rows))
    finally:
        for _, _, context, node, executor in objects:
            executor.shutdown(); node.destroy_node(); rclpy.shutdown(context=context)


if __name__ == '__main__':
    raise SystemExit(main())
