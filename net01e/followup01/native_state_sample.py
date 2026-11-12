"""Bounded read-only 50Hz observation of the actual owned native main PID."""
import argparse
import json
import os
from pathlib import Path
import time
import threading


def sample_owned_native(args, ready_event=None):
    args.directory.mkdir(exist_ok=False)
    target = Path('/proc', str(args.pid))
    initial_stat = (target / 'stat').read_text()
    actual_start_ticks = int(initial_stat.rsplit(')', 1)[1].split()[19])
    if actual_start_ticks != args.expected_start_ticks:
        raise RuntimeError('Owned native PID start identity changed before sampling')
    try:
        affinity = dict(cpus=sorted(os.sched_getaffinity(args.pid)))
    except OSError as error:
        affinity = dict(error=repr(error), errno=error.errno)
    try:
        fd_numbers = sorted({0, 1, 2} | {int(entry.name) for entry in (target / 'fd').iterdir()})
        fd_links = dict(maximum_links=64, truncated=len(fd_numbers) > 64, links={})
        for fd in fd_numbers[:64]:
            try:
                fd_links['links'][str(fd)] = dict(target=os.readlink(target / 'fd' / str(fd)))
            except OSError as error:
                fd_links['links'][str(fd)] = dict(error=repr(error), errno=error.errno)
    except OSError as error:
        fd_links = dict(error=repr(error), errno=error.errno)
    begin = time.monotonic_ns()
    deadline = min(args.work_deadline_ns, begin + 48_000_000_000)
    period = 20_000_000
    max_samples = 2400
    max_bytes = 8 * 1024 * 1024
    count = total_bytes = read_cpu_ns = read_wall_ns = 0
    reason = None
    if ready_event is not None:
        ready_event.set()
    with (args.directory / 'samples.jsonl').open('xb') as stream:
        while count < max_samples:
            before = time.monotonic_ns()
            if args.failure_file.exists():
                reason = 'original_FIRST_FAILURE'; break
            if args.stop_file.exists():
                reason = 'original_STOP'; break
            if before >= deadline:
                reason = 'original_work_or48wall_deadline'; break
            cpu_before = time.thread_time_ns()
            row = dict(index=count, begin_monotonic_ns=before, begin_thread_cpu_ns=cpu_before,
                       pid=args.pid, files={})
            for name in ('wchan', 'syscall', 'stat', 'schedstat', 'io'):
                try:
                    row['files'][name] = dict(text=(target / name).read_text())
                except OSError as error:
                    row['files'][name] = dict(error=repr(error), errno=error.errno)
            row['end_monotonic_ns'] = time.monotonic_ns()
            row['end_thread_cpu_ns'] = time.thread_time_ns()
            encoded = (json.dumps(row, separators=(',', ':')) + '\n').encode()
            if total_bytes + len(encoded) > max_bytes:
                reason = '8MiB_limit'; break
            stream.write(encoded)
            count += 1
            total_bytes += len(encoded)
            read_cpu_ns += row['end_thread_cpu_ns'] - cpu_before
            read_wall_ns += row['end_monotonic_ns'] - before
            if 'text' not in row['files']['stat'] and not target.exists():
                reason = 'actual_native_exited'; break
            # No catch-up bursts when observation itself is delayed.
            delay = (before + period - time.monotonic_ns()) / 1e9
            if delay > 0:
                time.sleep(delay)
        else:
            reason = '2400_sample_limit'
    result = dict(pid=args.pid, expected_start_ticks=args.expected_start_ticks,
        actual_start_ticks=actual_start_ticks, initial_affinity=affinity, initial_fd_links=fd_links,
        observer_host_pid=os.getpid(), observer_native_thread_id=threading.get_native_id(),
        begin_monotonic_ns=begin, end_monotonic_ns=time.monotonic_ns(),
        period_ns=period, maximum_samples=max_samples, maximum_bytes=max_bytes,
        work_deadline_ns=deadline, samples=count, bytes=total_bytes, end_reason=reason,
        read_wall_ns=read_wall_ns, read_thread_cpu_ns=read_cpu_ns,
        semantics='Raw /proc observations of only the owned native main PID; read brackets are not state-transition times. Missing/permission-denied values remain errors. Sampling at most50Hz may miss short waits; wall-minus-CPU does not prove a specific blocking cause. No native/ROS state, scheduling or IO priority is changed.')
    (args.directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--expected-start-ticks', type=int, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path, required=True)
    parser.add_argument('--failure-file', type=Path, required=True)
    parser.add_argument('--work-deadline-ns', type=int, required=True)
    args = parser.parse_args()
    sample_owned_native(args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
