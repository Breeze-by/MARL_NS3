"""Original Gateway with passive full-wire source capture for one new recording."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / 'net01')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path, required=True)
    parser.add_argument('--mode', choices=('A', 'B', 'C'), required=True)
    parser.add_argument('--dds-take-trace', action='store_true')
    args = parser.parse_args()
    from gateway import Gateway

    class CapturedGateway(Gateway):
        def __init__(self):
            self.wire_rows = []; self.wire_bodies = bytearray()
            super().__init__(args.mode, args.directory.parent / 'wire.sock', args.directory,
                             2026110912, dispatch_profile=True, control_trace=True,
                             dds_take_trace=args.dds_take_trace,
                             execution_profile='controlled1000-clock100-q10ms-pace10-raster-simhealth',
                             adapter_qos_events='warning-free-v1')

        def send(self, sender, receiver, flow, body, rpc_id=0, source_stamp_ns=0):
            row = dict(ordinal=len(self.wire_rows), sender=sender, receiver=receiver,
                       flow=flow, rpc_id=rpc_id, source_stamp_ns=source_stamp_ns,
                       source_sim_ns=self.gz, anchor=self.anchor,
                       capture_monotonic_ns=time.monotonic_ns(), body_offset=len(self.wire_bodies),
                       body_bytes=len(body), send_returned=False,
                       cdr_sha256=hashlib.sha256(body).hexdigest(),
                       source='new_original_component_wire_capture')
            if len(self.wire_bodies) + len(body) > 128 * 1024 * 1024:
                raise ValueError('new full-wire recording exceeds 128MiB bound')
            self.wire_rows.append(row); self.wire_bodies.extend(body)
            super().send(sender, receiver, flow, body, rpc_id, source_stamp_ns)
            row.update(send_returned=True, send_return_monotonic_ns=time.monotonic_ns())

    node = CapturedGateway(); failure = None
    try:
        print('COLLECTION_GATEWAY_READY', flush=True)
        while not args.stop_file.exists():
            node.poll()
            fault = node.failure or next((g.guard.fault for g in node.guards.values() if g.guard.fault), None)
            if fault and failure is None:
                failure = fault
                (args.directory.parent / 'FIRST_FAILURE.json').write_text(json.dumps(
                    dict(failure=fault, monotonic_ns=time.monotonic_ns(), scope='new collection')))
    finally:
        clean = node.close()
        (args.directory / 'wire-bodies.bin').write_bytes(node.wire_bodies)
        with (args.directory / 'wire-records.jsonl').open('x') as stream:
            for row in node.wire_rows:
                stream.write(json.dumps(row) + '\n')
        (args.directory / 'wire-manifest.json').write_text(json.dumps(dict(
            clean=clean, failure=failure, records=len(node.wire_rows), body_bytes=len(node.wire_bodies),
            scope='Actual newly executed original component send attempts, not historical original traffic. '
                  'Includes dynamic protocol traffic. Fixed-wire replay preserves these attempts as load; '
                  'it does not claim new per-arm application retry behavior.')) + '\n')
    return 0 if clean and failure is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
