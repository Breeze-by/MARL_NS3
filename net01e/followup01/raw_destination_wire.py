"""Destination-only CDR publish candidate; inherited source/QoS/queue semantics.

This deliberately isolated override mirrors TopicWire.receive except for its
last publish argument. Original deserialization, identity checks and trace
metadata remain; bytes use the installed public Publisher.publish_raw path.
"""
import hashlib
import time

from topic_wire import TopicWire, TFMessage, tf_headers, deserialize_message


class RawDestinationTopicWire(TopicWire):
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
            self.publishers[flow].publish(cdr)
            row["publisher_returned"]=True
        finally:
            row["publish_after_monotonic_ns"]=time.monotonic_ns()
            row["publish_after_thread_cpu_ns"]=time.thread_time_ns()
