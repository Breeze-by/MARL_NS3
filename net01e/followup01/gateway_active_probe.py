"""Inert child-only RAM snapshots over the unchanged collection Gateway."""
import copy
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def increments(start, end):
    """Subtract additive fields only; cumulative maxima are not window maxima."""
    cpu = {}
    for side in ('C', 'R'):
        cpu[side] = {}
        for category in ('wait', 'handlers'):
            left = start['cpu_profile'][side][category]
            right = end['cpu_profile'][side][category]
            cpu[side][category] = {name: {field: row[field] - left.get(name, {}).get(field, 0)
                for field in ('calls', 'wall_ns', 'thread_cpu_ns')}
                for name, row in right.items()}
    left = start['cpu_profile']['progress']
    cpu['progress'] = {name: {field: row[field] - left.get(name, {}).get(field, 0)
        for field in ('calls', 'wall_ns', 'thread_cpu_ns')}
        for name, row in end['cpu_profile']['progress'].items()}
    dispatch = {}
    for side in ('C', 'R'):
        dispatch[side] = {field: value - start['dispatch_stats'][side].get(field, 0)
            for field, value in end['dispatch_stats'][side].items()
            if field not in ('max_wall_s', 'max_cpu_s')}
    dispatch['idle_wait'] = {field: value - start['dispatch_stats']['idle_wait'][field]
        for field, value in end['dispatch_stats']['idle_wait'].items()
        if not field.startswith('max_')}
    return dict(cpu_profile=cpu, dispatch=dispatch,
        wall_between_snapshot_brackets_ns=end['copy_begin_monotonic_ns'] - start['copy_end_monotonic_ns'],
        thread_cpu_between_snapshot_brackets_ns=end['copy_begin_thread_cpu_ns'] - start['copy_end_thread_cpu_ns'],
        scope='First gz>=50 poll-entry to explicitly labelled end boundary; counters additive, no reset, no maxima subtraction',
        end_reason=end['end_reason'],
        inclusive_warning='poll_inclusive contains all stages; progress total_inclusive contains hub_poll/direct_batch. '
            'Side wait/handler spans exclude after-handler progress; side max_wall_s includes it. Do not sum inclusive parents and children.')


def main():
    admission = json.loads((HERE / 'ACTIVE_PROBE_ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True:
        raise RuntimeError('Inert source: Root pin and unique START required')
    sys.path[:0] = [str(REPO / 'net01'), str(REPO / 'net01e/replay'), str(REPO)]
    import gateway
    import collect_gateway

    original = gateway.Gateway

    class ActivePhaseGateway(original):
        def __init__(self, *args, **kwargs):
            self.active_phase = dict(start=None, end=None,
                trigger='First original public poll entry with already-observed R gz>=50sim',
                observations_only=True, original_poll_calls=0)
            self.normal_revocation_recorded = False
            super().__init__(*args, **kwargs)

        def snapshot(self, name, end_reason=None):
            begin = time.monotonic_ns()
            cpu = time.thread_time_ns()
            row = dict(cpu_profile=copy.deepcopy(self.cpu_profile),
                dispatch_stats=copy.deepcopy(self.dispatch_stats), gz_ns=self.gz,
                native_horizon_ns=self.hub.horizon_ns,
                failure=self.failure,
                end_reason=end_reason,
                guard_faults={str(robot): guardian.guard.fault for robot, guardian in self.guards.items()},
                original_poll_calls=self.active_phase['original_poll_calls'])
            cpu_end = time.thread_time_ns()
            row.update(copy_begin_monotonic_ns=begin, copy_end_monotonic_ns=time.monotonic_ns(),
                copy_begin_thread_cpu_ns=cpu, copy_end_thread_cpu_ns=cpu_end,
                copy_thread_cpu_ns=cpu_end - cpu)
            self.active_phase[name] = row

        def poll(self):
            if self.active_phase['start'] is None and self.gz is not None and self.gz >= 50_000_000_000:
                self.snapshot('start')
            result = super().poll()  # Full existing poll_inclusive accounting has finished on return.
            self.active_phase['original_poll_calls'] += 1
            if (self.active_phase['start'] is not None and self.active_phase['end'] is None
                    and (self.failure or any(g.guard.fault for g in self.guards.values()))):
                self.snapshot('end', 'first_original_fault_complete_poll_return')
            self.observe_normal_revocation()
            return result

        def observe_normal_revocation(self):
            if self.normal_revocation_recorded or self.failure or any(g.guard.fault for g in self.guards.values()):
                return
            authority = self.directory.parent / 'AUTHORITY_EXIT_CONFIRMED.json'
            if not authority.exists() or self.last_status is None:
                return
            cleanup = self.last_status['actual_rpc_cleanup']
            if any(cleanup.values()):
                return
            robots = {}
            for robot, local in self.guards.items():
                revoked = [row for row in local.guard.events if row['kind'] == 'control_permission_revoked']
                actual_revoked = [row for row in local.records if row['kind'] == 'actual_control_permission_revoked']
                pauses = [row for row in local.records if row['kind'] == 'actual_local_pause_response']
                if (not local.guard.halted or local.guard.armed or not revoked or not actual_revoked
                        or not any(row['success'] is True for row in pauses)
                        or local.owned or local.accepted or any(not future.done() for future in local.futures)):
                    return
                if self.last_status['gateway_monotonic_ns'] <= actual_revoked[-1]['monotonic_ns']:
                    return  # Do not use a pre-revocation zero-count status as closure evidence.
                robots[str(robot)] = dict(halted=local.guard.halted, armed=local.guard.armed,
                    fault=local.guard.fault, guard_revocation=revoked, actual_control_revocation=actual_revoked,
                    actual_pause_responses=pauses, owned=sorted(local.owned), accepted=sorted(local.accepted),
                    actual_terminals=dict(local.terminals), all_cleanup_futures_done=True,
                    actual_local_records=list(local.records))
            row = dict(observed_monotonic_ns=time.monotonic_ns(), gz_ns=self.gz,
                session_id=self.session_id, authority_exit_proof=json.loads(authority.read_text()),
                robots=robots, actual_rpc_cleanup=dict(cleanup),
                status_monotonic_ns=self.last_status['gateway_monotonic_ns'],
                scope='Observed original RAM revocation/PAUSE/ownership/RPC closure after actual fixture client exit; no safety override or physical-stop proof')
            marker = self.directory.parent / 'NORMAL_REVOKED_CLOSED.json'
            temporary = marker.with_suffix('.tmp')
            with temporary.open('x') as stream:
                json.dump(row, stream, indent=2)
                stream.write('\n')
            temporary.rename(marker)
            self.normal_revocation_recorded = True

        def close(self):
            if (self.active_phase['start'] is not None and self.active_phase['end'] is None
                    and self.failure is None and not any(g.guard.fault for g in self.guards.values())):
                self.snapshot('end', 'normal_close_no_original_fault')
            try:
                return super().close()
            finally:
                phase = self.active_phase
                if phase['start'] is not None and phase['end'] is not None:
                    phase['increment'] = increments(phase['start'], phase['end'])
                else:
                    phase['increment'] = None
                    phase['missing_window'] = 'No matching start/fault pair; do not substitute whole-life counters'
                with (self.directory / 'active-phase-profile.json').open('x') as stream:
                    json.dump(phase, stream, indent=2)
                    stream.write('\n')

    gateway.Gateway = ActivePhaseGateway
    try:
        return collect_gateway.main()
    finally:
        gateway.Gateway = original


if __name__ == '__main__':
    raise SystemExit(main())
