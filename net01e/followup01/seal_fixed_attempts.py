"""Inert until explicitly invoked: seal every recorded main-window send attempt."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

START = 50_000_000_000
END = 60_000_000_000
PREWARM = 3_000_000_000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.source/'wire-manifest.json').read_text())
    if not manifest['clean'] or manifest['failure'] is not None:
        raise ValueError('Selected source must be the accepted clean recording')
    if manifest['body_bytes'] > 128*1024*1024:
        raise ValueError('Original recording128MiB bound exceeded')
    args.output.mkdir(parents=True, exist_ok=False)
    counts = Counter(); selected = total = copied = 0; previous_due = -1
    with (args.source/'wire-records.jsonl').open() as rows, (args.source/'wire-bodies.bin').open('rb') as bodies, \
            (args.output/'attempts.jsonl').open('x') as output, (args.output/'bodies.bin').open('xb') as target:
        for line in rows:
            row = json.loads(line); total += 1
            if not START <= row['source_sim_ns'] < END:
                continue
            due = row['source_sim_ns']-START
            if due < previous_due:
                raise ValueError('Captured logical due order regressed; do not reorder attempts')
            previous_due = due
            bodies.seek(row['body_offset']); body = bodies.read(row['body_bytes'])
            if len(body) != row['body_bytes'] or hashlib.sha256(body).hexdigest() != row['cdr_sha256']:
                raise ValueError('Recorded body extent/content does not match existing record')
            sealed = dict(row, replay_ordinal=selected, source_ordinal=row['ordinal'],
                source_body_offset=row['body_offset'], body_offset=copied,
                relative_due_ns=due, native_admission_ns=PREWARM+due)
            output.write(json.dumps(sealed)+'\n'); target.write(body)
            counts[f"{row['sender']}->{row['receiver']}/flow{row['flow']}"] += 1
            selected += 1; copied += len(body)
    if total != manifest['records']:
        raise ValueError('Source record count differs from sealed manifest')
    (args.output/'manifest.json').write_text(json.dumps(dict(scope='Fixed recorded SEND ATTEMPTS, not reactive Action/ROS replay',
        source=str(args.source), source_manifest=manifest, original_records=total,
        window_start_ns=START,window_end_exclusive_ns=END,selected_attempts=selected,
        body_bytes=copied,flow_direction_counts=dict(counts),deduplicated=False,
        prewarm_native_ns=PREWARM,main_native_duration_ns=END-START,
        proposed_drain_native_ns=2_000_000_000,
        relative_due_semantics='Original Gateway source_sim_ns minus50sim; capture_monotonic_ns retained but wall jitter not regenerated. Same-due order is original ordinal.',
        preserved='Every attempt, including repeated RPC/CDR and send_returned flag. Original direction/flow/RPC/CDR/source stamp unchanged; offsets only repacked.',
        proposed_replay_status='NOT_ADMITTED_NOT_RUN'),indent=2)+'\n')


if __name__ == '__main__':
    main()
