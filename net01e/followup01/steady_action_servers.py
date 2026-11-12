"""Existing no-motion fixture with an explicit .01wall steady feedback timer."""
import argparse
import json
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'net01'))
sys.path.insert(0, str(REPO / 'net01e/replay'))


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--output', type=Path, required=True)
    args, _ = parser.parse_known_args()
    import check_action_wire
    import action_servers
    from rclpy.clock import Clock, ClockType
    original = check_action_wire.ControlledServer
    instances = []

    class SteadyControlledServer(original):
        def __init__(self, node, robot):
            self.feedback_generation = {}
            self.successful_tick_count = 0
            super().__init__(node, robot)
            node.destroy_timer(self.timer)
            self.feedback_clock = Clock(clock_type=ClockType.STEADY_TIME)
            self.timer = node.create_timer(.01, self.tick, clock=self.feedback_clock)
            instances.append(self)

        def tick(self):
            participants = tuple(self.executing)
            before = time.monotonic_ns()
            super().tick()
            after = time.monotonic_ns()
            self.successful_tick_count += 1
            for uuid in participants:
                entry = self.feedback_generation.setdefault(uuid, dict(count=0,
                    first_tick_begin_monotonic_ns=before,
                    first_tick_return_monotonic_ns=after))
                entry['count'] += 1
                entry['last_tick_begin_monotonic_ns'] = before
                entry['last_tick_return_monotonic_ns'] = after

    check_action_wire.ControlledServer = SteadyControlledServer
    try:
        action_servers.main()
    finally:
        check_action_wire.ControlledServer = original
        report = dict(clock_type='STEADY_TIME', configured_period_wall_s=.01,
            robots={str(server.robot): dict(successful_tick_count=server.successful_tick_count,
                per_uuid=server.feedback_generation) for server in instances},
            semantics='Each UUID count is one original publish_feedback in a successfully returned original tick. Tick begin/return bracket the publication; no exact internal publish timestamp is claimed. An exception propagates and that incomplete tick is not counted. Configuration is not measured achieved Hz.',
            unchanged='Original feedback fields, Goal52/release54/cancel55 sim, execute/cancel/result and PAUSE/ARM logic; no Nav2 or movement.')
        args.output.with_name('feedback-generation.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
