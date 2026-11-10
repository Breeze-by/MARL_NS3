"""Opt-in observations for this installed Humble executor's single native take.

Only R TF subscriptions are observed. SDK execution/awaiting and callback groups
are inherited unchanged. Metadata is the actual second tuple item, not inferred
arrival time; this SDK exposes source_timestamp/received_timestamp, not writerGID.
"""
import time

from rclpy.executors import SingleThreadedExecutor


class MetadataSingleThreadedExecutor(SingleThreadedExecutor):
    def __init__(self, *, context, node, trace):
        super().__init__(context=context)
        self._trace_node = node
        self._take_trace = trace
        self._tf_flows = {f'/tb{r}/tf':r*20+3 for r in (1,2,3)}

    def _take_subscription(self, sub):
        flow = self._tf_flows.get(sub.topic_name)
        if flow is None:
            return super()._take_subscription(sub)
        row = self._take_trace.stamp('R_TF_take',flow=flow,
            topic=sub.topic_name,raw=sub.raw,
            ros_sim_before_ns=self._trace_node.get_clock().now().nanoseconds)
        row.update(before_realtime_ns=time.time_ns(),
            before_realtime_mono_after_ns=time.monotonic_ns(),original_returned=False)
        try:
            # This is the installed SDK's same one take and same tuple[0].
            with sub.handle:
                msg_info = sub.handle.take_message(sub.msg_type, sub.raw)
                if msg_info is not None:
                    row['metadata'] = msg_info[1]
                    value = msg_info[0]
                else:
                    row['metadata'] = None
                    value = None
            row.update(original_returned=True,taken=value is not None,
                ros_sim_after_ns=self._trace_node.get_clock().now().nanoseconds)
            if value is not None and not sub.raw:
                row['tf_edges'] = [dict(frame_id=t.header.frame_id,
                    child_frame_id=t.child_frame_id,
                    stamp_ns=t.header.stamp.sec*1_000_000_000+t.header.stamp.nanosec)
                    for t in value.transforms]
            return value
        except BaseException as error:
            row['exception'] = repr(error)
            raise
        finally:
            row.update(end_mono_ns=time.monotonic_ns(),end_thread_cpu_ns=time.thread_time_ns(),
                end_realtime_ns=time.time_ns(),end_realtime_mono_after_ns=time.monotonic_ns())
