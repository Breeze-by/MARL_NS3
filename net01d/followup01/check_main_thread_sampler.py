"""One stdlib-only controlled observer check. 0ROS/Node/ns3/Gazebo."""
import argparse
import json
from pathlib import Path
import time
from main_thread_sampler import MainThreadSampler


def sleep_work():time.sleep(.08)


def cpu_work():
    end=time.monotonic()+.08
    value=0
    while time.monotonic()<end:value+=1
    return value


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=False)
    sampler=MainThreadSampler();sampler.start();phases={}
    try:
        for name,work in [('sleep',sleep_work),('CPU',cpu_work)]:
            begin=time.monotonic_ns();cpu=time.thread_time_ns();work()
            phases[name]=dict(begin_mono_ns=begin,end_mono_ns=time.monotonic_ns(),
                main_cpu_ns=time.thread_time_ns()-cpu)
    finally:stop=sampler.stop()
    snapshot=sampler.snapshot();found={}
    path=args.directory/'sampler.json'
    with path.open('x') as stream:json.dump(snapshot,stream,indent=2)
    rows=snapshot['rows'] if not snapshot['samples_unavailable'] else []
    for phase,function in [('sleep','sleep_work'),('CPU','cpu_work')]:
        found[phase]=[row for row in rows if phases[phase]['begin_mono_ns']<=row['stack_mono_ns']<=phases[phase]['end_mono_ns']
            and any(frame['function']==function for frame in row['stack'])]
    exclusive=False
    try:
        with path.open('x'):pass
    except FileExistsError:exclusive=True
    checks=dict(sleep_stack_captured=bool(found['sleep']),CPU_stack_captured=bool(found['CPU']),
        main_CPU_clock_reads_valid=all(row['main_cpu_after_ns']>=row['main_cpu_before_ns'] for row in rows),
        CPU_phase_used_more_CPU_than_sleep=phases['CPU']['main_cpu_ns']>phases['sleep']['main_cpu_ns'],
        actual_context_switch_fields=any(row['proc']['status']['valid'] for row in rows),
        observer_joined_after_stop=stop['joined'] and not sampler.thread.is_alive(),
        observer_failure_absent=stop['failure'] is None,exclusive_save_refuses_overwrite=exclusive,
        closed_snapshot_delivered=not snapshot['samples_unavailable'],
        proc_FDs_closed=stop['proc_fds_remaining']==0 and not stop['proc_close_errors'],
        actual_schedule_and_lateness_recorded=all('scheduled_mono_ns' in row and
            row['start_lateness_ns']==row['start_mono_ns']-row['scheduled_mono_ns']
            and 'skipped_periods_after' in row for row in rows))
    validity={name:sum(row['proc'][name]['valid'] for row in rows) for name in ('status','wchan','syscall','schedstat')}
    result=dict(scope='One real stdlib observer check; 80ms sleep +80msCPU; no ROS/Node/robot/native/Gazebo',
        status='PASS' if all(checks.values()) else 'FAIL',checks=checks,phases=phases,
        samples_per_phase={k:len(v) for k,v in found.items()},proc_valid_reads=validity,
        kernel_sched_schedstats=snapshot['kernel_sched_schedstats'],stop=stop,
        context_switch_ranges={name:([min(values),max(values)] if values else None)
            for name in ('voluntary_ctxt_switches','nonvoluntary_ctxt_switches')
            for values in [[row['proc']['status'][name] for row in rows if row['proc']['status']['valid']]]},
        interpretation='Context switches and futex can include observer GIL competition; one row is not cause attribution')
    with (args.directory/'result.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result));return 0 if all(checks.values()) else 1


if __name__=='__main__':raise SystemExit(main())
