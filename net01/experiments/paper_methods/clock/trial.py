#!/usr/bin/python3 -B
"""Fixed, synthetic-clock, latest-value IPC comparison; no simulator imports."""
import argparse
import bisect
import json
import mmap
import multiprocessing as mp
from pathlib import Path
import socket
import struct
import sys
import tempfile
import time
import traceback

PERIOD = 1_000_000
SOURCE_WALL = 3_000_000_000
READER_WALL = 3_100_000_000
CASES = ('baseline', 'reader_pause', 'source_pause')


def wait_until(target):
    remaining = target - time.monotonic_ns()
    if remaining > 0:
        time.sleep(remaining / 1e9)


def next_tick(epoch):
    # Remain phase-aligned, without a catch-up burst after descheduling.
    return epoch + ((time.monotonic_ns() - epoch) // PERIOD + 1) * PERIOD


def save(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, separators=(',', ':'))
        stream.write('\n')


def source(case, shared, connection, control, output):
    rows, flushes, backpressure = [], [], []
    pending = bytearray()
    enqueued = sent = sequence = 0
    error = None
    cpu_start = time.process_time_ns()
    import os
    pid = os.getpid()
    try:
        with shared.open('r+b') as stream, mmap.mmap(stream.fileno(), 8) as slot:
            connection.setblocking(False)
            control.send(('ready', pid))
            epoch = control.recv()
            tick = epoch

            def flush():
                nonlocal sent
                while pending:
                    try:
                        count = connection.send(pending)
                    except BlockingIOError:
                        backpressure.append([time.monotonic_ns(), sent, len(pending)])
                        break
                    if count == 0:
                        raise RuntimeError('zero-byte socket send')
                    del pending[:count]
                    sent += count
                    flushes.append([time.monotonic_ns(), sent, len(pending)])

            while True:
                wait_until(tick)
                now = time.monotonic_ns()
                if now >= epoch + SOURCE_WALL:
                    break
                if case == 'source_pause' and epoch + 1_000_000_000 <= now < epoch + 1_350_000_000:
                    flush()
                    tick = next_tick(epoch)
                    continue
                sequence += 1
                clock_ns = sequence * PERIOD
                generation = time.monotonic_ns()
                frame = json.dumps(dict(seq=sequence, clock_ns=clock_ns), separators=(',', ':')).encode() + b'\n'
                row = dict(seq=sequence, clock_ns=clock_ns, generation_ns=generation,
                           order='shm_first' if sequence % 2 else 'uds_first')

                def put_shm():
                    row['shm_begin_ns'] = time.monotonic_ns()
                    struct.pack_into('=Q', slot, 0, clock_ns)
                    row['shm_return_ns'] = time.monotonic_ns()

                def put_uds():
                    nonlocal enqueued
                    row['uds_enqueue_ns'] = time.monotonic_ns()
                    pending.extend(frame)
                    enqueued += len(frame)
                    row['uds_frame_end_offset'] = enqueued
                    flush()
                    row['uds_pending_bytes_after'] = len(pending)

                if sequence % 2:
                    put_shm(); put_uds()
                else:
                    put_uds(); put_shm()
                rows.append(row)
                tick = next_tick(epoch)
            flush()
            if pending:
                raise RuntimeError('source exited with unsent bytes')
    except BaseException:
        error = traceback.format_exc()
        raise
    finally:
        loop_end = time.monotonic_ns()
        cpu = time.process_time_ns() - cpu_start
        connection.close()  # EOF is real; SHM has no writer-liveness signal.
        control.close()
        save(output / 'source.json', dict(case=case, pid=pid, epoch_ns=locals().get('epoch'),
             source='controlled synthetic clock; not Gazebo', error=error, rows=rows, flushes=flushes,
             backpressure=backpressure,
             source_loop_end_ns=loop_end, process_cpu_ns=cpu, unsent_bytes=len(pending),
             enqueued_bytes=enqueued, sent_bytes=sent))


def receiver(case, transport, shared, connection, control, output):
    rows, pauses = [], []
    buffer = bytearray()
    value = 0
    eof = False
    error = None
    cpu_start = time.process_time_ns()
    import os
    pid = os.getpid()
    stream = slot = None
    try:
        if transport == 'shm':
            stream = shared.open('rb')
            slot = mmap.mmap(stream.fileno(), 8, access=mmap.ACCESS_READ)
        else:
            connection.setblocking(False)
        control.send(('ready', pid))
        epoch = control.recv()
        tick = epoch
        paused = False
        while True:
            wait_until(tick)
            now = time.monotonic_ns()
            if now >= epoch + READER_WALL:
                break
            if case == 'reader_pause' and not paused and now >= epoch + 1_000_000_000:
                begin = time.monotonic_ns()
                wait_until(epoch + 1_140_000_000)
                pauses.append(dict(begin_ns=begin, end_ns=time.monotonic_ns(), held_clock_ns=value))
                paused = True
            begin, cpu = time.monotonic_ns(), time.thread_time_ns()
            newest, complete = value, 0
            if transport == 'shm':
                newest = struct.unpack_from('=Q', slot, 0)[0]
            elif not eof:
                while True:
                    try:
                        body = connection.recv(65536)
                    except BlockingIOError:
                        break
                    if not body:
                        eof = True
                        break
                    buffer.extend(body)
                while b'\n' in buffer:
                    raw, _, rest = buffer.partition(b'\n')
                    buffer = bytearray(rest)
                    frame = json.loads(raw)
                    if frame['clock_ns'] != frame['seq'] * PERIOD:
                        raise RuntimeError('clock/sequence mismatch')
                    newest = max(newest, frame['clock_ns'])
                    complete += 1
            receipt = time.monotonic_ns()
            cpu = time.thread_time_ns() - cpu
            if newest < value or newest % PERIOD:
                raise RuntimeError('nonmonotonic or invalid clock value')
            rows.append(dict(read_begin_ns=begin, receipt_ns=receipt, read_cpu_ns=cpu,
                clock_ns=newest, new=newest != value, complete_frames=complete,
                buffered_bytes=len(buffer), source_eof=eof))
            value = newest
            tick = next_tick(epoch)
        if buffer:
            raise RuntimeError('receiver ended with an incomplete frame')
    except BaseException:
        error = traceback.format_exc()
        raise
    finally:
        loop_end = time.monotonic_ns()
        cpu = time.process_time_ns() - cpu_start
        if slot is not None:
            slot.close(); stream.close()
        if connection is not None:
            connection.close()
        control.close()
        save(output / (transport + '.json'), dict(case=case, transport=transport, pid=pid,
             epoch_ns=locals().get('epoch'), error=error, polls=rows, pauses=pauses,
             loop_end_ns=loop_end, process_cpu_ns=cpu,
             semantics='latest only; repeated value is not a new generation'))


def distribution(values):
    if not values:
        return None
    ordered = sorted(values)
    return dict(count=len(ordered), min=ordered[0], median=ordered[len(ordered)//2],
                p95=ordered[min(len(ordered)-1, int(.95 * len(ordered)))], max=ordered[-1])


def summarize(output, exits):
    src = json.loads((output / 'source.json').read_text())
    generated = {r['clock_ns']: r for r in src['rows']}
    offsets = [r[1] for r in src['flushes']]
    summary = dict(exits=exits, source_generations=len(generated), transports={})
    for transport in ('shm', 'uds'):
        data = json.loads((output / (transport + '.json')).read_text())
        polls = data['polls']
        ages, new_ages, publication_ages = [], [], []
        observed = set()
        for row in polls:
            if row['clock_ns'] == 0:
                continue
            generation = generated[row['clock_ns']]
            age = row['receipt_ns'] - generation['generation_ns']
            ages.append(age)
            if row['new']:
                observed.add(row['clock_ns']); new_ages.append(age)
                if transport == 'shm':
                    publication = generation['shm_return_ns']
                else:
                    index = bisect.bisect_left(offsets, generation['uds_frame_end_offset'])
                    publication = src['flushes'][index][0]
                publication_ages.append(row['receipt_ns'] - publication)
        pauses = [dict(p, held_source_age_at_end_ns=p['end_ns']-generated[p['held_clock_ns']]['generation_ns'])
                  for p in data['pauses'] if p['held_clock_ns'] in generated]
        summary['transports'][transport] = dict(
            generation_to_new_receipt_ns=distribution(new_ages),
            publication_return_to_new_receipt_ns=distribution(publication_ages),
            observed_source_age_ns=distribution(ages),
            source_age_over_300ms_polls=sum(a > 300_000_000 for a in ages),
            poll_interval_ns=distribution([b['read_begin_ns']-a['read_begin_ns'] for a,b in zip(polls,polls[1:])]),
            read_cpu_ns=distribution([r['read_cpu_ns'] for r in polls]),
            read_cpu_total_ns=sum(r['read_cpu_ns'] for r in polls),
            process_cpu_ns=data['process_cpu_ns'], polls=len(polls), pauses=pauses,
            complete_frames=sum(r['complete_frames'] for r in polls),
            missed_generations=len(generated)-len(observed),
            final_clock_ns=polls[-1]['clock_ns'] if polls else None,
            real_EOF_observed=any(r['source_eof'] for r in polls), error=data['error'])
    save(output / 'summary.json', summary)
    return summary


def run_case(context, case, output):
    output.mkdir(exist_ok=False)
    owned = []
    deadline = time.monotonic() + 15
    with tempfile.TemporaryDirectory(prefix='net01-clock-') as temp:
        shared = Path(temp) / 'clock.u64'
        with shared.open('xb') as f:
            f.write(b'\0' * 8)
        sender, reader = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        # spawn passes only the explicitly named endpoints to each child.
        for name, target, args in (
            ('source', source, (case, shared, sender)),
            ('shm', receiver, (case, 'shm', shared, None)),
            ('uds', receiver, (case, 'uds', shared, reader))):
            parent, child = context.Pipe()
            process = context.Process(target=target, args=(*args, child, output), name=name)
            process.start(); child.close()
            owned.append((name, process, parent))
        sender.close(); reader.close()
        try:
            ready = {}
            for name, process, control in owned:
                if not control.poll(max(0, deadline-time.monotonic())):
                    raise TimeoutError('readiness deadline: ' + name)
                ready[name] = control.recv()
                if ready[name][0] != 'ready':
                    raise RuntimeError('invalid readiness: ' + name)
            epoch = time.monotonic_ns() + 100_000_000
            for _, _, control in owned:
                control.send(epoch)
            save(output / 'identity.json', dict(case=case, epoch_ns=epoch, ready=ready,
                source_wall_ns=SOURCE_WALL, reader_wall_ns=READER_WALL, nominal_period_ns=PERIOD,
                boundary='synthetic clock; no ROS/ns3/Gazebo', actual_argv=sys.argv,
                uds='AF_UNIX SOCK_STREAM socketpair; no IP network'))
            for name, process, _ in owned:
                process.join(max(0, deadline-time.monotonic()))
                if process.is_alive():
                    raise TimeoutError('case hard deadline: ' + name)
        finally:
            forced = []
            for name, process, control in owned:
                if process.is_alive():
                    forced.append(name); process.kill(); process.join(1)
                control.close()
            exits = {name: process.exitcode for name, process, _ in owned}
            save(output / 'process-exit.json', dict(exits=exits, forced=forced))
        if forced or any(code != 0 for code in exits.values()):
            raise RuntimeError('case child failure; original artifacts retained')
    return summarize(output, exits)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(exist_ok=False)
    context = mp.get_context('spawn')
    summaries = {}
    try:
        for case in CASES:
            summaries[case] = run_case(context, case, args.output / case)
    finally:
        save(args.output / 'run.json', dict(cases=summaries, configuration='PLAN.md fixed cases',
            scope='development IPC trial only; no statistical significance or simulation qualification'))


if __name__ == '__main__':
    main()
