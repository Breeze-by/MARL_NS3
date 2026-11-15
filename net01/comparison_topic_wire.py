"""Same original CDR capture/publish, with passive same-take source provenance."""
from comparison_measurement import _context, SOURCE_TOPICS
from consumer_topic_wire import ConsumerTraceTopicWire


class ComparisonTopicWire(ConsumerTraceTopicWire):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        original_send = self.send
        self._comparison_owner = getattr(original_send, '__self__', None)
        def send(*args, **kwargs):
            row = self.captured[-1]
            previous = getattr(_context, 'capture', None)
            _context.capture = row
            try:
                result = original_send(*args, **kwargs)
                row['source_send_returned'] = True
                # Mode A uses the existing exact direct FIFO sequence.
                owner = getattr(original_send, '__self__', None)
                if owner is not None and owner.mode == 'A':
                    row['direct_native_id'] = owner.direct_sequence
                return result
            finally:
                _context.capture = previous
        self.send = send

    def receive(self, meta, cdr, rpc_id):
        begin = len(self.delivered)
        owner = self._comparison_owner
        witnessed = None if owner is None else owner.gz
        try:
            return super().receive(meta, cdr, rpc_id)
        finally:
            if len(self.delivered)>begin:
                self.delivered[begin]['gateway_receive_clock_ns'] = witnessed

    def capture(self, flow, message):
        topic = self.specs[flow]['topic']
        source = self.node._comparison_take_trace.pop(topic, message) if topic in SOURCE_TOPICS else None
        begin = len(self.captured)
        owner = self._comparison_owner
        witnessed = None if owner is None else owner.gz
        try:
            return super().capture(flow, message)
        finally:
            if len(self.captured) > begin:
                row = self.captured[begin]
                row['capture_seq'] = begin + 1
                row['source_topic'] = topic
                row['source_take'] = source
                row['gateway_capture_clock_ns'] = witnessed
