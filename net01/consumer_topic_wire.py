"""Passive timestamps around the existing raw-CDR Gateway publication.

Receive identity/deserialization, original complete CDR and publisher/QoS stay
with RawDestinationTopicWire. No extra subscription, take, publish or payload.
"""
import time

from raw_destination_wire import RawDestinationTopicWire


class ConsumerTraceTopicWire(RawDestinationTopicWire):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._publication_sequences = {}
        for flow, publisher in self.publishers.items():
            original = publisher.publish
            def publish(cdr, flow=flow, original=original):
                before_wall, before_cpu = time.monotonic_ns(), time.thread_time_ns()
                row = self.delivered[-1]
                sequence = self._publication_sequences.get(flow, 0) + 1
                self._publication_sequences[flow] = sequence
                row.update(gateway_publication_seq=sequence,
                    gateway_publication_topic=self.specs[flow].get('received_topic', self.specs[flow]['topic']),
                    gateway_publication_side=self.side,
                    publish_before_realtime_ns=time.time_ns(),
                    publish_before_realtime_monotonic_after_ns=time.monotonic_ns())
                pre_wall, pre_cpu = time.monotonic_ns() - before_wall, time.thread_time_ns() - before_cpu
                try:
                    return original(cdr)
                finally:
                    after_wall, after_cpu = time.monotonic_ns(), time.thread_time_ns()
                    row.update(publish_after_realtime_ns=time.time_ns(),
                        publish_after_realtime_monotonic_after_ns=time.monotonic_ns())
                    row.update(consumer_trace_diagnostic_wall_ns=pre_wall + time.monotonic_ns() - after_wall,
                        consumer_trace_diagnostic_thread_cpu_ns=pre_cpu + time.thread_time_ns() - after_cpu)
            publisher.publish = publish
