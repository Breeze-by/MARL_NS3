"""Original typed ROS topics transported as full CDR, separate R/C domains.

The supplied send callback owns actual transport. This module never republishes
from a source cache; receive() accepts only complete destination wire messages.
"""
import time
import hashlib
from rclpy.serialization import serialize_message, deserialize_message
from rclpy.qos import QoSProfile, DurabilityPolicy
from nav_msgs.msg import OccupancyGrid, Odometry
from std_msgs.msg import String
from tf2_msgs.msg import TFMessage
from nav2_msgs.msg import CostmapFilterInfo
from geometry_msgs.msg import Twist


def flows(*, runtime=False):
    output = {}
    for robot in (1, 2, 3):
        prefix = f"/tb{robot}"
        for offset, name, cls, depth, transient in [
            (1, "map", OccupancyGrid, 10, True),
            (2, "odom", Odometry, 10, False),
            (3, "tf", TFMessage, 100, False),
            (4, "tf_static", TFMessage, 100, True),
            (5, "local_costmap/costmap", OccupancyGrid, 1, True),
            *(([(6, "cmd_vel", Twist, 4, False)]) if runtime else []),
        ]:
            output[robot*20+offset] = dict(robot=robot, direction="up", topic=prefix+"/"+name,
                cls=cls, depth=depth, transient=transient)
        for offset, name, cls in [(10, "peer_keepout_mask", OccupancyGrid),
                                  (11, "peer_keepout_state", String),
                                  (12, "peer_keepout_filter_info", CostmapFilterInfo)]:
            # One original C health producer fans out over three real STA links.
            # Only STA1 feeds the original public Observer topic; the other two
            # remain separately named for their independent local watchdogs.
            source_topic = "/peer_keepout_state" if offset == 11 else prefix+"/"+name
            received_topic = ("/peer_keepout_state" if robot == 1 else prefix+"/peer_keepout_state") if offset == 11 else source_topic
            output[robot*20+offset] = dict(robot=robot, direction="down", topic=source_topic,
                received_topic=received_topic, cls=cls, depth=1, transient=offset != 11)
    if runtime:
        output[89] = dict(robot=1,direction="down",topic="/merge_map",
            cls=OccupancyGrid,depth=10,transient=True)
        output[95] = dict(robot=1,direction="down",topic="/net01/controller_records",
            cls=String,depth=100,transient=False)
    return output


def qos(spec):
    return QoSProfile(depth=spec["depth"], durability=(DurabilityPolicy.TRANSIENT_LOCAL
        if spec["transient"] else DurabilityPolicy.VOLATILE))


def tf_headers(message):
    """Value-only provenance; never replace or reserialize a transform."""
    return [dict(frame_id=t.header.frame_id,child_frame_id=t.child_frame_id,
        stamp_ns=t.header.stamp.sec*1_000_000_000+t.header.stamp.nanosec)
        for t in message.transforms]


class TopicWire:
    def __init__(self, node, side, send, *, bound_masks=False, runtime=False):
        if side not in ("R", "C"):
            raise ValueError("Explicit R or C endpoint required")
        self.node, self.side, self.send = node, side, send
        self.specs = flows(runtime=runtime)
        if bound_masks:
            self.specs = {f:s for f,s in self.specs.items() if f%20!=10}
        self.publishers, self.subscriptions = {}, []
        self.captured, self.delivered = [], []
        for flow, spec in self.specs.items():
            outgoing = (side == "R") == (spec["direction"] == "up")
            if outgoing:
                self.subscriptions.append(node.create_subscription(spec["cls"], spec["topic"],
                    lambda message, f=flow: self.capture(f, message), qos(spec)))
            else:
                self.publishers[flow] = node.create_publisher(spec["cls"],
                    spec.get("received_topic", spec["topic"]), qos(spec))

    def capture(self, flow, message):
        now = time.monotonic_ns()
        body = serialize_message(message)
        spec = self.specs[flow]
        header = getattr(message, "header", None)
        stamp = 0 if header is None else header.stamp.sec*1_000_000_000+header.stamp.nanosec
        row=dict(flow=flow, robot=spec["robot"], bytes=len(body),
            cdr_sha256=hashlib.sha256(body).hexdigest(),
            source_stamp_ns=stamp, source_stamp_available=header is not None,
            endpoint_capture_monotonic_ns=now,
            capture_node_sim_ns=self.node.get_clock().now().nanoseconds)
        if spec["cls"] is TFMessage:row["tf_edges"]=tf_headers(message)
        self.captured.append(row)
        sender, receiver = (spec["robot"], 0) if self.side == "R" else (0, spec["robot"])
        self.send(sender, receiver, flow, body, 0, stamp)

    def receive(self, meta, cdr, rpc_id):
        flow = meta["flow"]
        spec = self.specs[flow]
        expected_sender, expected_receiver = ((spec["robot"], 0) if spec["direction"] == "up" else (0, spec["robot"]))
        if (meta["sender"], meta["receiver"]) != (expected_sender, expected_receiver) or rpc_id != 0 or flow not in self.publishers:
            raise ValueError("Cross-robot/direction/topic identity violation")
        message = deserialize_message(cdr, spec["cls"])
        row=dict(meta, cdr_bytes=len(cdr),
            cdr_sha256=hashlib.sha256(cdr).hexdigest(),
            destination_node_sim_ns=self.node.get_clock().now().nanoseconds,
            publisher_returned=False)
        if spec["cls"] is TFMessage:row["tf_edges"]=tf_headers(message)
        self.delivered.append(row)
        row["endpoint_publish_monotonic_ns"]=time.monotonic_ns()
        row["publish_before_thread_cpu_ns"]=time.thread_time_ns()
        try:
            self.publishers[flow].publish(message)
            row["publisher_returned"]=True
        finally:
            row["publish_after_monotonic_ns"]=time.monotonic_ns()
            row["publish_after_thread_cpu_ns"]=time.thread_time_ns()
