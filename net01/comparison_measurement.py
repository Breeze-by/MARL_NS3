"""Passive same-take source cohorts; no added reader, frame or business data."""
from contextlib import contextmanager
import json
from pathlib import Path
import threading
import time

from hub_client import HubClient

VERSION = 'source-take-v1'
SOURCE_TOPICS = frozenset(f'/tb{r}/{name}' for r in (1, 2, 3)
                          for name in ('map', 'odom', 'tf', 'tf_static'))
_context = threading.local()


def clock(node):
    return dict(realtime_ns=time.time_ns(), monotonic_ns=time.monotonic_ns(),
                sim_ns=node.get_clock().now().nanoseconds)


class TakeTrace:
    def __init__(self, node, retain_pending=False):
        self.node, self.retain_pending = node, retain_pending
        self.rows, self.pending = [], {}
        self.cpu_ns = self.wall_ns = 0

    @contextmanager
    def diagnostic(self):
        wall, cpu = time.monotonic_ns(), time.thread_time_ns()
        try: yield
        finally:
            self.cpu_ns += time.thread_time_ns() - cpu
            self.wall_ns += time.monotonic_ns() - wall

    def take(self, sub):
        with self.diagnostic(): before = clock(self.node)
        with sub.handle:
            result = sub.handle.take_message(sub.msg_type, sub.raw)
        with self.diagnostic():
            after = clock(self.node)
            if result is not None:
                message, metadata = result
                row = dict(take_seq=len(self.rows)+1, topic=sub.topic_name,
                    before=before, after=after, metadata=metadata, publisher_gid=None)
                self.rows.append(row)
                if self.retain_pending:
                    self.pending[(sub.topic_name, id(message))] = row
        return None if result is None else result[0]

    def pop(self, topic, message):
        return self.pending.pop((topic, id(message)), None)


def install_take_trace(node, executor, retain_pending=False, subscription_selector=None):
    trace = TakeTrace(node, retain_pending)
    original = executor._take_subscription
    membership = {}
    def take(sub):
        if sub not in membership:
            membership[sub] = (sub.topic_name in SOURCE_TOPICS and
                (subscription_selector(sub) if subscription_selector is not None else
                 any(sub is item for item in node.subscriptions)))
        if membership[sub]:
            return trace.take(sub)
        return original(sub)
    executor._take_subscription = take
    node._comparison_take_trace = trace
    return trace


def install_source_observer(node, executor):
    return install_take_trace(node, executor)


def finish_source_observer(node):
    trace = node._comparison_take_trace
    directory = Path(node.directory)
    with (directory/'source-observer-takes.jsonl').open('x') as stream:
        for row in trace.rows: stream.write(json.dumps(row)+'\n')
    with (directory/'source-observer-measurement.json').open('x') as stream:
        json.dump(dict(rows=len(trace.rows), diagnostic_wall_ns=trace.wall_ns,
            diagnostic_thread_cpu_ns=trace.cpu_ns,
            scope='Existing R Observer received-publication cohort; not a count of all original publisher emissions; source_timestamp is DDS publication time, not generation AoI'), stream)


def install_gateway_takes(gateway):
    for node, executor in zip(gateway.nodes, gateway.executors):
        def selected(sub, node=node):
            return gateway.wires is not None and any(sub is item
                for wire in gateway.wires.values() if wire.node is node for item in wire.subscriptions)
        install_take_trace(node, executor, retain_pending=True, subscription_selector=selected)


class ComparisonHubClient(HubClient):
    def __init__(self, *args, **kwargs):
        self.comparison_send_seq = 0
        self.comparison_sends = []
        super().__init__(*args, **kwargs)

    def frame(self, meta, body=b''):
        if meta['kind'] == 'send':
            self.comparison_send_seq += 1
            capture = getattr(_context, 'capture', None)
            if capture is not None:
                capture['hub_send_seq'] = self.comparison_send_seq
                self.comparison_sends.append(dict(send_seq=self.comparison_send_seq,
                    sender=meta['sender'], receiver=meta['receiver'], flow=meta['flow'],
                    bytes=len(body), admission_ns=meta.get('admission_ns'),
                    source_stamp_ns=meta.get('source_stamp_ns')))
        return super().frame(meta, body)


def persist_gateway_measurement(gateway):
    with (Path(gateway.directory)/'comparison-gateway.json').open('x') as stream:
        json.dump(dict(sends=gateway.hub.comparison_sends,
            send_seq_total=gateway.hub.comparison_send_seq,
            source_take_diagnostics=[dict(rows=len(node._comparison_take_trace.rows),
                pending=len(node._comparison_take_trace.pending),
                wall_ns=node._comparison_take_trace.wall_ns,
                thread_cpu_ns=node._comparison_take_trace.cpu_ns) for node in gateway.nodes],
            semantics='send_seq must be verified against actual hub-ingress native_message_id and unchanged route/size/admission; no hash used as generation identity'), stream)
