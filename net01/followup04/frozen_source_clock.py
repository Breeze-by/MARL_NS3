"""Fixture timing only: configured sim-rate ceilings, not a robot/SLAM model."""


class FrozenSourceClock:
    def __init__(self):
        self.sim_ns = self.origin_ns = self.scan_header_ns = None
        self.ticks = dict(odom=0, wheel=0, scan=0)
        self.skipped_configured_ticks = dict(odom=0, wheel=0, scan=0)
        self.last_costmap_ns = {robot: 0 for robot in (1, 2, 3)}

    def advance(self, sim_ns):
        if self.sim_ns is None:
            self.sim_ns = self.origin_ns = self.scan_header_ns = sim_ns
            return set()
        if sim_ns < self.sim_ns:
            raise ValueError('Actual source clock rollback')
        self.sim_ns = sim_ns
        due = set()
        for kind, hz in (('odom', 30), ('wheel', 10), ('scan', 5)):
            tick = (sim_ns - self.origin_ns) * hz // 1_000_000_000
            if tick > self.ticks[kind]:
                self.skipped_configured_ticks[kind] += tick - self.ticks[kind] - 1
                self.ticks[kind] = tick  # Skip missed ticks; never replay old samples.
                due.add(kind)
        if 'scan' in due:
            self.scan_header_ns = sim_ns
        return due

    def costmap_due(self, robot, node_sim_ns):
        # Nav2 checks this strict ROS-time predicate in its 5Hz wall update loop.
        if node_sim_ns > self.last_costmap_ns[robot] + 500_000_000:
            self.last_costmap_ns[robot] = node_sim_ns
            return True
        return False


def wheel_message(stamp_ns):
    from geometry_msgs.msg import TransformStamped
    from tf2_msgs.msg import TFMessage
    transforms = []
    for child in ('wheel_left_link', 'wheel_right_link'):
        transform = TransformStamped()
        transform.header.frame_id = 'base_link'
        transform.child_frame_id = child
        transform.header.stamp.sec = stamp_ns // 1_000_000_000
        transform.header.stamp.nanosec = stamp_ns % 1_000_000_000
        transform.transform.rotation.w = 1.
        transforms.append(transform)
    return TFMessage(transforms=transforms)
