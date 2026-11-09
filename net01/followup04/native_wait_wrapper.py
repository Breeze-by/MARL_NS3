#!/usr/bin/python3 -B
"""Read-only5ms parent sampler; NATIVE DIAGNOSTIC_DIR [original native argv...]."""
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time


def main():
    native,directory,*arguments=sys.argv[1:]
    directory=Path(directory)
    if directory.parent!=Path('/dev/shm'):
        raise ValueError('Diagnostic directory must be an exclusive /dev/shm child')
    directory.mkdir(exist_ok=False)
    usage_start=resource.getrusage(resource.RUSAGE_SELF)
    machine=os.uname().machine
    wall_start=time.monotonic_ns();process=None;child_usage=None;exit_code=1
    pending_signal=None;samples=0;max_sample_wall_ns=0
    def requested(signum,frame):
        nonlocal pending_signal
        pending_signal=signum
    signal.signal(signal.SIGINT,requested);signal.signal(signal.SIGTERM,requested)
    with (directory/'trace.jsonl').open('x',buffering=1) as stream:
        def record(kind,**fields):
            stream.write(json.dumps(dict(kind=kind,monotonic_ns=time.monotonic_ns(),
                realtime_ns=time.time_ns(),**fields),separators=(',',':'))+'\n')
            stream.flush()
        def reap(options):
            nonlocal child_usage,exit_code
            pid,status,usage=os.wait4(process.pid,options)
            if pid:
                child_usage=usage;exit_code=os.waitstatus_to_exitcode(status)
                process.returncode=exit_code
            return bool(pid)
        def read(name):
            try:return (Path('/proc')/str(process.pid)/name).read_text().strip()
            except OSError as error:return dict(errno=error.errno,error=str(error))
        record('wrapper_start',wrapper_pid=os.getpid(),actual_wrapper_argv=sys.argv,
            actual_child_argv=[native,*arguments],period_ns=5_000_000,
            clock_ticks_per_second=os.sysconf('SC_CLK_TCK'),machine=machine,
            stdio='FD0/1/2 inherited directly; no pipe/protocol proxy')
        try:
            process=subprocess.Popen([native,*arguments],stdin=None,stdout=None,stderr=None)
            record('child_started',child_pid=process.pid)
            while not reap(os.WNOHANG):
                if pending_signal is not None:break
                begin=time.monotonic_ns();row={}
                stat=read('stat')
                if isinstance(stat,str):
                    fields=stat[stat.rfind(')')+2:].split()
                    row.update(state=fields[0],utime_ticks=int(fields[11]),stime_ticks=int(fields[12]),
                        minfault=int(fields[7]),majfault=int(fields[9]),nice=int(fields[16]),policy=int(fields[38]))
                else:row['stat_error']=stat
                schedstat=read('schedstat')
                if isinstance(schedstat,str):
                    running,runqueue,slices=map(int,schedstat.split())
                    row.update(running_ns=running,runqueue_ns=runqueue,timeslices=slices)
                else:row['schedstat_error']=schedstat
                row['wchan']=read('wchan');row['syscall']=read('syscall')
                # This native host is x86_64. Decode only the FD of write-like
                # syscalls; retain the original string and every permission error.
                if machine=='x86_64' and isinstance(row['syscall'],str):
                    parts=row['syscall'].split()
                    if parts and parts[0]!='running' and int(parts[0],0) in (1,18,20,296,328):
                        fd=int(parts[1],0);row['write_fd']=fd
                        try:row['write_fd_target']=os.readlink(f'/proc/{process.pid}/fd/{fd}')
                        except OSError as error:row['write_fd_error']=dict(errno=error.errno,error=str(error))
                elapsed=time.monotonic_ns()-begin
                max_sample_wall_ns=max(max_sample_wall_ns,elapsed);samples+=1
                record('sample',child_pid=process.pid,sample_begin_monotonic_ns=begin,
                    proc_read_wall_ns=elapsed,**row)
                # No catch-up burst after descheduling; actual timestamps expose
                # any missed5ms interval rather than adding extra sampler load.
                remaining=(begin+5_000_000-time.monotonic_ns())/1e9
                if remaining>0:time.sleep(remaining)
            if pending_signal is not None and process.returncode is None:
                record('forward_signal_to_child',signal=pending_signal)
                try:os.kill(process.pid,pending_signal)
                except ProcessLookupError:pass
        except BaseException as error:
            record('wrapper_error',error=repr(error))
        finally:
            if process is not None and process.returncode is None:
                # Only this direct child is collected. The original fixture's
                # hard wall deadline remains external and unchanged.
                if pending_signal is None:
                    try:process.terminate()
                    except ProcessLookupError:pass
                until=time.monotonic()+1
                while not reap(os.WNOHANG) and time.monotonic()<until:time.sleep(.005)
                if process.returncode is None:
                    record('force_child_kill')
                    try:process.kill()
                    except ProcessLookupError:pass
                    reap(0)
            own=resource.getrusage(resource.RUSAGE_SELF)
            keys=('ru_utime','ru_stime','ru_maxrss','ru_minflt','ru_majflt',
                'ru_inblock','ru_oublock','ru_nvcsw','ru_nivcsw')
            record('wrapper_end',actual_child_exit=exit_code,samples=samples,
                elapsed_wall_ns=time.monotonic_ns()-wall_start,max_proc_read_wall_ns=max_sample_wall_ns,
                wrapper_user_s=own.ru_utime-usage_start.ru_utime,
                wrapper_system_s=own.ru_stime-usage_start.ru_stime,
                wrapper_total_user_s=own.ru_utime,wrapper_total_system_s=own.ru_stime,
                child_rusage=None if child_usage is None else {key:getattr(child_usage,key) for key in keys})
    return exit_code


if __name__=='__main__':
    code=main()
    if code<0:
        # Preserve the child's signal status rather than turning -SIG into an
        # unrelated modulo256 normal exit code.
        if -code!=signal.SIGKILL:signal.signal(-code,signal.SIG_DFL)
        os.kill(os.getpid(),-code)
    raise SystemExit(code)
