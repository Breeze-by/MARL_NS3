"""Post-run cleanup of the one CLI daemon belonging to a closed NET case."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import time

REPO = Path(__file__).resolve().parent.parent


def recorded_pids(case):
    pids = set()
    paths = (case / 'owned_processes.jsonl',
             case.with_name(case.name + '.time-control') / 'owned.jsonl',
             case.with_name(case.name + '.owned-runner.json'),
             case.with_name(case.name + '.native-load.json'))
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text()
        rows = ([json.loads(line) for line in text.splitlines()]
                if path.suffix == '.jsonl' else [json.loads(text)])
        for row in rows:
            for key in ('pid', 'bwrap_pid', 'child_pid', 'hub_pid'):
                if row.get(key):
                    pids.add(row[key])
    launch = case / 'launch.log'
    if launch.exists():
        pids.update(int(pid) for pid in re.findall(
            r'process started with pid \[(\d+)\]', launch.read_text()))
    return sorted(pids)


def cleanup_owned_cli_daemon(case, session_id, domain_id, output):
    """Call only after the host has ended its original owned resources."""
    case, output = Path(case).resolve(), Path(output)
    marker = '/mnt/' + str(case.relative_to(REPO))
    closed = recorded_pids(case)
    alive = [pid for pid in closed if Path(f'/proc/{pid}').exists()]
    if alive:
        raise RuntimeError('Original recorded processes still exist: ' + repr(alive))
    argv = ['/usr/bin/python3', '-c',
            'from ros2cli.daemon.daemonize import main; main()',
            '--name', 'ros2-daemon', '--ros-domain-id', str(domain_id),
            '--rmw-implementation', 'rmw_fastrtps_cpp']
    expected = dict(GZ01_CASE=marker, NET01_SESSION_ID=str(session_id),
                    ROS_DOMAIN_ID=str(domain_id), RMW_IMPLEMENTATION='rmw_fastrtps_cpp')

    def identity(pid):
        proc = Path('/proc') / str(pid)
        try:
            if proc.stat().st_uid != os.getuid():
                return None
            actual_argv = [v.decode() for v in (proc / 'cmdline').read_bytes().split(b'\0') if v]
            if actual_argv != argv:
                return None
            env = dict(v.decode().split('=', 1) for v in
                       (proc / 'environ').read_bytes().split(b'\0') if b'=' in v)
            if any(env.get(k) != v for k, v in expected.items()):
                return None
            start = int((proc / 'stat').read_text().rsplit(')', 1)[1].split()[19])
            return dict(pid=pid, start_ticks=start, argv=actual_argv, markers=expected,
                        uid=proc.stat().st_uid)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            return None

    matches = [row for proc in Path('/proc').iterdir() if proc.name.isdigit()
               and (row := identity(int(proc.name))) is not None]
    if len(matches) > 1:
        raise RuntimeError('Ambiguous owned CLI daemon; no signal sent')
    output.mkdir(parents=True, exist_ok=False)
    result = dict(start_utc=datetime.now(timezone.utc).isoformat(), case=str(case),
                  session_id=session_id, domain_id=domain_id,
                  original_recorded_pids=closed, all_recorded_pids_gone=True,
                  matches=matches, signals=[], timeout_wall_s=12,
                  exit_code=None, exit_code_scope='Not our child; never infer exit0',
                  no_TERM_or_KILL=True)
    (output / 'before.json').write_text(json.dumps(result, indent=2) + '\n')
    if matches:
        row = matches[0]
        fd = os.pidfd_open(row['pid'])
        try:
            if identity(row['pid']) != row:
                raise RuntimeError('Daemon identity changed; no signal sent')
            signal.pidfd_send_signal(fd, signal.SIGINT)
            result['signals'].append(dict(pid=row['pid'], signal='SIGINT', via='pidfd'))
            begin = time.monotonic()
            while Path(f'/proc/{row["pid"]}').exists() and time.monotonic() - begin < 12:
                time.sleep(.05)
            result['wait_wall_s'] = time.monotonic() - begin
            result['target_process_exited'] = not Path(f'/proc/{row["pid"]}').exists()
        finally:
            os.close(fd)
    else:
        result['target_process_exited'] = None
    result['cleanup_pass'] = not matches or result['target_process_exited']
    result['end_utc'] = datetime.now(timezone.utc).isoformat()
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    ready = json.loads(args.ready.read_text())
    case = REPO / ready['case_relative_phase']
    host = json.loads(case.with_name(case.name + '.host-exit.json').read_text())
    if not host.get('end_utc') or host.get('controlled_time', {}).get('remaining_owned_groups'):
        raise RuntimeError('Host resource closure not recorded')
    result = cleanup_owned_cli_daemon(case, ready['network']['session_id'],
                                      ready['network']['domain_R'], args.output)
    print(json.dumps(result, indent=2))
    return 0 if result['cleanup_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
