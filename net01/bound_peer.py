"""Observe frozen real peer publications; bind each original mask to its batch.

The frozen computation/publications still run, in their original order. This
external adapter adds transport provenance, never recomputes a mask or pose.
"""
import argparse
from array import array
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

FROZEN_WORKSPACE = Path(__file__).resolve().parents[1] / "workspace"
sys.path.insert(0, str(FROZEN_WORKSPACE / "gz01"))
sys.path.insert(0, str(FROZEN_WORKSPACE / "src/multi_robot_exploration"))
import peer_keepout as frozen
import rclpy
from rclpy.qos import QoSProfile, DurabilityPolicy
from rclpy.serialization import serialize_message, deserialize_message
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import UInt8MultiArray


class ObservedPublisher:
    def __init__(self, publisher, after):
        self.publisher, self.after = publisher, after

    def publish(self, message):
        self.publisher.publish(message)
        self.after(message)


class BatchBinding:
    def __init__(self, publish_bound, session_id):
        self.publish_bound = publish_bound
        self.session_id = session_id
        self.pending = {}
        self.records = []

    def mask(self, robot, message):
        if robot in self.pending:
            raise RuntimeError("Two masks before this original batch health")
        body = bytes(serialize_message(message))
        self.pending[robot] = (body, dict(stamp_sec=message.header.stamp.sec,
            stamp_nanosec=message.header.stamp.nanosec, frame_id=message.header.frame_id))

    def health(self, message):
        if set(self.pending) != set(frozen.ROBOTS):
            raise RuntimeError("Cannot bind incomplete actual publication batch")
        state = json.loads(message.data)
        # Values are copied only from this actual health message, never from
        # an asynchronously received 'latest' state or simulator ground truth.
        source = {name:state[name] for name in ("ready", "generated_sim", "sequence", "odom_stamps", "correction_stamps")}
        health_sha = hashlib.sha256(serialize_message(message)).hexdigest()
        for robot in frozen.ROBOTS:
            body, header = self.pending[robot]
            meta = dict(version="mask-publication-batch-v1", session_id=self.session_id,
                robot=robot, original_header=header, mask_cdr_bytes=len(body),
                mask_cdr_sha256=hashlib.sha256(body).hexdigest(), health_cdr_sha256=health_sha,
                bound_state=source, captured_monotonic_ns=time.monotonic_ns())
            encoded = json.dumps(meta, separators=(",", ":")).encode()
            # Exact original CDR is the body. Metadata and mask travel together.
            packet = struct.pack("!I", len(encoded))+encoded+body
            self.publish_bound(robot, packet)
            self.records.append(meta)
        self.pending.clear()


def decode_envelope(packet, robot, session_id):
    if len(packet) < 4:
        raise ValueError("Missing mask binding")
    size, = struct.unpack("!I", packet[:4])
    if size > len(packet)-4:
        raise ValueError("Truncated mask binding")
    meta = json.loads(packet[4:4+size])
    body = packet[4+size:]
    if meta["version"] != "mask-publication-batch-v1" or meta["robot"] != robot or meta["session_id"] != session_id:
        raise ValueError("Mask robot/session/binding mismatch")
    if len(body) != meta["mask_cdr_bytes"] or hashlib.sha256(body).hexdigest() != meta["mask_cdr_sha256"]:
        raise ValueError("Actual mask CDR identity mismatch")
    return meta, body


def decode_bound(packet, robot, session_id):
    meta, body = decode_envelope(packet, robot, session_id)
    message = deserialize_message(body, OccupancyGrid)
    h = meta["original_header"]
    if (message.header.stamp.sec,message.header.stamp.nanosec,message.header.frame_id) != (h["stamp_sec"],h["stamp_nanosec"],h["frame_id"]):
        raise ValueError("Mask header differs from actual bound source")
    return meta, message


class BoundPeer(frozen.PeerKeepout):
    def __init__(self, scene, directory, *, session_id):
        self.tf_input_records=[]
        super().__init__(scene,directory,timing=False)
        qos = QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.bound_publishers = {r:self.create_publisher(UInt8MultiArray,
            f"/net01/{r}/peer_mask_bound",qos) for r in frozen.ROBOTS}
        self.binding = BatchBinding(self.publish_bound,session_id)
        for robot in frozen.ROBOTS:
            self.maps[robot] = ObservedPublisher(self.maps[robot],
                lambda message,r=robot:self.binding.mask(r,message))
        self.health = ObservedPublisher(self.health,self.binding.health)

    def receive_tf(self,message,robot,static):
        # Observe the actual original callback exactly once. No new Buffer
        # query, input queue, subscription, filtering or stamp adjustment.
        row=dict(robot=robot,static=static,before_monotonic_ns=time.monotonic_ns(),
            before_node_sim_ns=self.get_clock().now().nanoseconds,
            held_correction_stamp_before=self.correction_stamps.get(robot),
            tf_edges=[dict(frame_id=t.header.frame_id,child_frame_id=t.child_frame_id,
                stamp_ns=t.header.stamp.sec*1_000_000_000+t.header.stamp.nanosec)
                for t in message.transforms],original_returned=False)
        try:
            value=super().receive_tf(message,robot,static)
            row["original_returned"]=True
            return value
        finally:
            row.update(after_monotonic_ns=time.monotonic_ns(),
                after_node_sim_ns=self.get_clock().now().nanoseconds,
                held_correction_stamp_after=self.correction_stamps.get(robot))
            self.tf_input_records.append(row)

    def publish_bound(self, robot, packet):
        self.bound_publishers[robot].publish(UInt8MultiArray(data=array("B",packet)))

    def persist_records(self):
        super().persist_records()
        with (self.directory/"bound-mask-publications.jsonl").open("x") as stream:
            for record in self.binding.records:
                stream.write(json.dumps(record)+"\n")
        with (self.directory/"bound-peer-tf-calls.jsonl").open("x") as stream:
            for record in self.tf_input_records:stream.write(json.dumps(record)+"\n")
        (self.directory/"bound-mask-recording-saved.json").write_text(json.dumps(dict(
            saved=True,mask_records=len(self.binding.records),tf_callback_records=len(self.tf_input_records),
            pending_undelimited_masks=len(self.binding.pending)))+"\n")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--scene",type=Path,required=True)
    parser.add_argument("--directory",type=Path,required=True)
    parser.add_argument("--session-id",type=int,required=True)
    args,ros_args=parser.parse_known_args()
    rclpy.init(args=ros_args)
    node=BoundPeer(json.loads(args.scene.read_text()),args.directory,session_id=args.session_id)
    try:rclpy.spin(node)
    finally:
        try:node.persist_records()
        finally:node.destroy_node();rclpy.shutdown()


if __name__=="__main__":main()
