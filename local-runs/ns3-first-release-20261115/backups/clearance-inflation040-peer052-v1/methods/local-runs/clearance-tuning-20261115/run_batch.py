#!/usr/bin/env python3
"""Serial manifest driver. Dry-run never starts host, Gazebo or native children.

Execution remains disabled until the reviewed plan supplies final READY paths,
post-exit verification/analysis commands and a structured classification result.
The production host retains all process ownership, deadlines and stopping logic.
"""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess


CONTINUE = {
    'QUALIFIED_REACHED_CONTINUE',
    'QUALIFIED_UNREACHED_CONTINUE',
}
RECEIPT_FIELDS = {
    'health_heartbeat_stale': 'health_receipt_sim',
    'bound_mask_receipt_stale': 'mask_receipt_sim',
}
ENGINEERING_GATES = (
    'identity_config_source', 'clock', 'pacing', 'actual_attempt_timing',
    'adapter_process', 'independent_wall_progress', 'evidence_complete',
)


def read(path):
    return json.loads(path.read_text())


def append(path, slot, state, **fields):
    row = dict(slot=slot, state=state,
               utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), **fields)
    with path.open('a') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    return row


def prior_states(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return {row['slot']: row for row in rows}


def command(argv, repo, log_path, on_start=None):
    # No shell, timeout escalation or second child-process management scheme.
    with log_path.open('x') as log:
        process = subprocess.Popen(argv, cwd=repo, stdout=log, stderr=subprocess.STDOUT)
        if on_start:
            on_start(process.pid)
        while True:
            try:
                return process.wait(timeout=45)
            except subprocess.TimeoutExpired:
                print(json.dumps(dict(progress='original owned command still running',
                                      pid=process.pid, log=str(log_path))), flush=True)


def verify_post_exit(proof, slot):
    required = ('all_owners_writers_gone', 'copy_complete', 'disk_raw_retained',
                'original_safe_stop', 'owned_requests_closed')
    if not all(proof.get(key) is True for key in required):
        raise RuntimeError('Post-exit safety/copy proof incomplete; no analysis or RAM release')
    if proof['case_relative_repo'] != slot['case_relative_repo']:
        raise RuntimeError('Post-exit case ownership mismatch')
    if proof['native_evidence_ram'] != slot['native_evidence_ram']:
        raise RuntimeError('Post-exit RAM ownership mismatch')


def receipt_protection_eligible(result, *, preautonomy=False):
    """Exact original sim-receipt protection; never infer cause from error text."""
    gates = result.get('engineering_checks', {})
    required = [key for key in ENGINEERING_GATES if not (preautonomy and key == 'pacing')]
    if not all(gates.get(key) is True for key in required):
        return False
    if preautonomy and not (result.get('autonomous_window_started') is False
            and result.get('autonomous_pacing_status') == 'N/A_NO_AUTONOMY'
            and gates.get('pacing') is None):
        return False
    if result.get('earlier_engineering_faults') != [] or result.get('unclassified_faults') != []:
        return False
    if result.get('original_outcome_retained') is not True:
        return False
    faults = result.get('receipt_protection_events')
    if not faults:
        return False
    for event in faults:
        field = RECEIPT_FIELDS.get(event.get('reason'))
        context = event.get('progress_context', {})
        if (event.get('kind') != 'latched_INVALID' or field is None
                or event.get('receipt_clock_basis') != 'R-ros-sim-v1'
                or context.get('control_mode') != 'RUN'
                or 'control_failure' not in context or context['control_failure'] is not None):
            return False
        receipt = context.get(field+'_ns')
        limit = context.get(field.replace('_sim','_limit_ns'))
        now = event.get('sim_ns')
        if any(type(value) is not int for value in (now,receipt,limit)):
            return False
        if limit!=600_000_000 or not now-receipt>limit:
            return False
    return True


def window_valid_poststop_eligible(result):
    """Amendment01: window evidence survives a proven post-stop SIGTERM exit.

    This never upgrades the original process/network outcome or uses T95.
    """
    return (result.get('task_window_measurement_qualified') is True
        and result.get('full_engineering_qualified') is False
        and result.get('clean_exit') is False
        and result.get('original_run_stop_network_qualification') is False
        and result.get('original_run_integrity') is True
        and result.get('poststop_exit_proof',{}).get('pass_') is True
        and all(result.get('engineering_checks',{}).get(k) is True for k in ENGINEERING_GATES)
        and result.get('earlier_engineering_faults')==[]
        and result.get('unclassified_faults')==[]
        and result.get('receipt_protection_events')==[]
        and result.get('measurement_errors')==[])


def classification(result):
    if result.get('autonomous_window_started') is not True:
        return 'ENGINEERING_BLOCK_STOP_ROOT_REVIEW'
    gates = result.get('engineering_checks', {})
    if not all(gates.get(key) is True for key in ENGINEERING_GATES):
        return 'ENGINEERING_BLOCK_STOP_ROOT_REVIEW'
    if result.get('earlier_engineering_faults') != [] or result.get('unclassified_faults') != []:
        return 'ENGINEERING_BLOCK_STOP_ROOT_REVIEW'
    if result.get('original_run_stop_network_qualification') is True:
        return ('QUALIFIED_REACHED_CONTINUE' if result['T95_sim_s'] is not None
                else 'QUALIFIED_UNREACHED_CONTINUE')
    if window_valid_poststop_eligible(result):
        return 'WINDOW_VALID_POSTSTOP_EXIT_FAILURE_CONTINUE'
    if receipt_protection_eligible(result):
        return 'TASK_INFORMATION_FRESHNESS_PROTECTION'
    return 'ENGINEERING_BLOCK_STOP_ROOT_REVIEW'


def release_ram(repo, slot, proof, output):
    verify_post_exit(proof, slot)
    expected = '/dev/shm/ct15-' + slot['id']
    if slot['native_evidence_ram'] != expected:
        raise RuntimeError('RAM release is restricted to this exact task slot')
    ram = Path(expected)
    if ram.is_symlink():
        raise RuntimeError('Refuse symlink RAM release')
    if ram.exists():
        shutil.rmtree(ram)
    with output.open('x') as stream:
        stream.write(json.dumps(dict(released=True, source=expected,
            disk_raw_retained=True, proof=proof['proof_relative_repo'],
            utc=datetime.datetime.now(datetime.timezone.utc).isoformat()), indent=2) + '\n')


def dry_slot(repo, slot, journal, previous):
    if previous:
        if previous['state'] in CONTINUE:
            return
        raise RuntimeError('Previously claimed/unresolved/blocked slot cannot be started again')
    append(journal, slot['id'], 'CLAIMED', dry_run=True)
    append(journal, slot['id'], 'HOST_STARTED', dry_run=True, actual_process_started=False)
    append(journal, slot['id'], 'QUALIFIED_UNREACHED_CONTINUE', dry_run=True,
           T95=None, note='Synthetic orchestration state only; not an experiment or metric')


def execute_slot(repo, slot, journal, previous):
    if previous:
        if previous['state'] in CONTINUE:
            return
        raise RuntimeError('Previously claimed/unresolved/blocked slot requires root reconciliation')
    ready_path = repo / slot['ready_relative_repo']
    ready = read(ready_path)
    if not all(ready.get(key) is True for key in
               ('execution_authorized', 'authorized_gz01_execution', 'authorized_net01_execution')):
        raise RuntimeError('Slot has no reviewed READY execution authorization')
    hooks = slot['batch_hooks']
    # The initial hook invokes the existing unused/resource/native gates only.
    # It must not start Gazebo/native or mark this slot as attempted.
    if command(hooks['pre_start_argv'], repo, repo / hooks['pre_start_log']) != 0:
        raise RuntimeError('Original pre-START resource/identity/unused gate blocked')
    append(journal, slot['id'], 'CLAIMED', ready=str(ready_path))
    host_argv = ['python3', '-B', 'net01e/followup01/production_host.py', '--ready', str(ready_path)]
    append(journal, slot['id'], 'HOST_DISPATCH', argv=host_argv)
    host_exit = command(host_argv, repo, repo / hooks['host_log'],
        on_start=lambda pid: append(journal, slot['id'], 'HOST_STARTED', pid=pid))
    append(journal, slot['id'], 'HOST_EXITED', returncode=host_exit)
    if command(hooks['post_exit_verify_argv'], repo, repo / hooks['post_exit_verify_log']) != 0:
        raise RuntimeError('Post-exit owner/stop/copy verification blocked')
    proof = read(repo / hooks['post_exit_proof'])
    verify_post_exit(proof, slot)
    append(journal, slot['id'], 'POST_EXIT_COPY_PROVEN', proof=hooks['post_exit_proof'])
    for index, argv in enumerate(hooks['analysis_argv']):
        append(journal, slot['id'], 'ANALYSIS_CLAIMED', index=index, argv=argv)
        if command(argv, repo, repo / hooks['analysis_logs'][index]) != 0:
            raise RuntimeError('Declared analysis failed; preserve output and stop without retry')
    result = read(repo / hooks['classified_result'])
    if result.get('classification_contract') != 'clearance-tuning6-root-reviewed-v1':
        raise RuntimeError('Classification contract is not the reviewed batch contract')
    outcome = classification(result)
    release_ram(repo, slot, proof, repo / hooks['ram_release_result'])
    append(journal, slot['id'], outcome, result=hooks['classified_result'])
    if outcome not in CONTINUE:
        raise RuntimeError('Engineering failure preserved; queue stopped for root review')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=Path(__file__).with_name('PLAN.draft.json'))
    parser.add_argument('--journal', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--execute-reviewed', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    plan = read(args.plan)
    journal = args.journal.resolve()
    if args.execute_reviewed:
        if not plan.get('execution_authorized') or not plan.get('batch_execution_enabled'):
            raise RuntimeError('Plan and final batch hooks are not authorized for execution')
        if journal != Path(__file__).resolve().with_name('execution.jsonl'):
            raise RuntimeError('Real execution must use this task single canonical journal')
    journal.parent.mkdir(parents=True, exist_ok=True)
    lock_path = (Path(__file__).resolve().with_name('execution.lock') if args.execute_reviewed
                 else journal.with_suffix(journal.suffix + '.lock'))
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = prior_states(journal)
        if args.execute_reviewed and any(row.get('dry_run') for row in previous.values()):
            raise RuntimeError('Synthetic dry-run state cannot be consumed as actual experiments')
        for slot in plan['slots']:
            action = dry_slot if args.dry_run else execute_slot
            try:
                action(repo, slot, journal, previous.get(slot['id']))
            except Exception as error:
                append(journal, slot['id'], 'ENGINEERING_BLOCK_STOP_ROOT_REVIEW',
                       error=repr(error), dry_run=args.dry_run)
                raise
            if (args.execute_reviewed and slot['id']==plan.get('root_review_after_slot')
                    and plan.get('root_review_completed') is not True):
                append(journal,'CONTROL','ROOT_REVIEW_CHECKPOINT',after_slot=slot['id'],
                    scope='Unconditional formal baseline review; no score/coverage/motion selection. No nextslot or finalSUMMARY dispatched.')
                print(json.dumps(dict(status='ROOT_REVIEW_CHECKPOINT',after_slot=slot['id'],
                    review_completed=False,journal=str(journal))),flush=True)
                return
        if args.execute_reviewed:
            prior = prior_states(journal).get('BATCH')
            if prior is not None and prior['state'] != 'SUMMARY_COMPLETE':
                raise RuntimeError('Unresolved batch summary requires root reconciliation')
            if prior is None:
                append(journal,'BATCH','SUMMARY_CLAIMED')
                script = Path(__file__).resolve().with_name('post_case.py')
                code = command(['python3','-B',str(script),'summary','--plan',str(args.plan.resolve())],
                               repo,script.with_name('summary-driver.log'))
                if code != 0:
                    append(journal,'BATCH','ENGINEERING_BLOCK_STOP_ROOT_REVIEW',returncode=code)
                    raise RuntimeError('Final summary failed; preserve partial outputs without retry')
                append(journal,'BATCH','SUMMARY_COMPLETE')
    print(json.dumps(dict(status='dry-run completed' if args.dry_run else 'batch completed',
                          declared_slots=len(plan['slots']), journal=str(journal))), flush=True)


if __name__ == '__main__':
    main()
