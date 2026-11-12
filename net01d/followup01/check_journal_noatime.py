"""One owned-ext4, 0Node check of actual journal methods; no ROS import."""
import argparse
import ast
import errno
import fcntl
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace


def load_method(path, *, candidate, opens):
    source = path.read_text()
    tree = ast.parse(source)
    if candidate:
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Gateway')
        method = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == '_export_controller_records')
    else:
        method = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    def real_open(filename, flags):
        fd = os.open(filename, flags)
        opens.append(dict(fd=fd, flags=fcntl.fcntl(fd, fcntl.F_GETFL)))
        return fd
    namespace = dict(json=json, String=lambda **kwargs: SimpleNamespace(**kwargs),
                     os=SimpleNamespace(open=real_open, O_NOATIME=os.O_NOATIME))
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['_export_controller_records']


def read_noatime(path):
    with open(path, 'rb', opener=lambda filename, flags: os.open(filename, flags | os.O_NOATIME)) as stream:
        return stream.read()


def check(directory):
    directory.mkdir(parents=True, exist_ok=False)
    checks, observations, outputs, cursors = [], {}, {}, {}
    def require(name, value, **detail):
        checks.append(dict(name=name, passed=bool(value), **detail))
        assert value, name
    result = dict(scope='0Node actual AST journal methods on new owned files only; not a kernel-latency or Gateway timing test',
                  checks=checks, observations=observations, ROS_init=0, Node=0, ns3=0, Gazebo=0)
    try:
        here = Path(__file__).resolve().parent
        selected = lambda kind, value: json.dumps(dict(kind=kind, value=value), ensure_ascii=False)
        initial = (selected('rl_actual_nav2_goal_request', '目标一') + '\n' +
                   selected('feedback', '不导出') + '\n' +
                   selected('rl_actual_nav2_goal_response', '接受') + '\n' +
                   selected('rl_actual_nav2_goal_result', '半行结果'))
        append = '\n' + selected('rl_halt_requested', '停止') + '\n'
        for label, candidate in [('baseline', False), ('candidate', True)]:
            root = directory / label
            (root / 'controller').mkdir(parents=True)
            path = root / 'controller/allocation-events.jsonl'
            path.write_bytes(initial.encode('utf-8'))
            info = path.stat()
            old_atime = time.time_ns() - 2 * 24 * 3600 * 1_000_000_000
            os.utime(path, ns=(old_atime, info.st_mtime_ns))
            opens, published = [], []
            method = load_method(here.parent.parent / 'net01/gateway.py' if candidate else here / 'baseline_journal_excerpt.py',
                                 candidate=candidate, opens=opens)
            state = SimpleNamespace(directory=root, wires=object(), journal_position=0,
                                    journal_pub=SimpleNamespace(publish=lambda msg: published.append(msg.data)))
            snapshots = []
            for stage in ('partial', 'append', 'empty'):
                if stage == 'append':
                    with path.open('a') as stream:
                        stream.write(append)
                before = path.stat()
                method(state)
                after = path.stat()
                snapshots.append(dict(stage=stage, atime_before_ns=before.st_atime_ns,
                    atime_after_ns=after.st_atime_ns, mtime_before_ns=before.st_mtime_ns,
                    mtime_after_ns=after.st_mtime_ns, cursor=state.journal_position,
                    published=list(published)))
                require(label + '_' + stage + '_read_preserves_mtime', before.st_mtime_ns == after.st_mtime_ns)
                expected = initial if stage == 'partial' else initial + append
                require(label + '_' + stage + '_read_preserves_content', read_noatime(path) == expected.encode('utf-8'))
                if candidate:
                    for row in opens:
                        try:
                            os.fstat(row['fd'])
                        except OSError as error:
                            require('candidate_FD_closed_' + stage, error.errno == errno.EBADF)
                        else:
                            require('candidate_FD_closed_' + stage, False)
            observations[label] = dict(path=str(path), owner_uid=path.stat().st_uid,
                current_euid=os.geteuid(), opens=opens, reads=snapshots)
            outputs[label] = [row['published'] for row in snapshots]
            cursors[label] = [row['cursor'] for row in snapshots]
        old = observations['baseline']['reads'][0]
        new = observations['candidate']['reads'][0]
        require('baseline_real_read_updates_preset_old_atime', old['atime_after_ns'] > old['atime_before_ns'])
        require('candidate_all_real_reads_preserve_atime', all(r['atime_after_ns'] == r['atime_before_ns'] for r in observations['candidate']['reads']))
        require('candidate_kernel_F_GETFL_has_O_NOATIME', len(observations['candidate']['opens']) == 3 and
                all(r['flags'] & os.O_NOATIME for r in observations['candidate']['opens']))
        require('baseline_candidate_original_line_output_equal', outputs['baseline'] == outputs['candidate'])
        require('baseline_candidate_original_TextIO_cursor_equal', cursors['baseline'] == cursors['candidate'])
        require('partial_not_emitted_then_append_once_and_filter',
                [len(rows) for rows in outputs['candidate']] == [2, 4, 4] and
                [json.loads(row)['kind'] for row in outputs['candidate'][-1]] ==
                ['rl_actual_nav2_goal_request', 'rl_actual_nav2_goal_response', 'rl_actual_nav2_goal_result', 'rl_halt_requested'])
        require('owned_files_same_uid', all(r['owner_uid'] == r['current_euid'] for r in observations.values()))
        result['status'] = 'PASS'
    except BaseException as error:
        result.update(status='FAIL', error=repr(error))
        raise
    finally:
        with (directory / 'result.json').open('x') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps(dict(status=result.get('status'), checks_true=sum(r['passed'] for r in checks),
                              checks_total=len(checks), directory=str(directory)), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    check(parser.parse_args().directory)
