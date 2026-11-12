"""Opt-in bounded-process main-thread observer. No ROS/socket/business ownership.

Proc snapshots are non-atomic and GIL competition changes context switches.
Never attribute a wait to one wchan sample or interpret disabled run_delay=0.
"""
import os
from pathlib import Path
import sys
import threading
import time


class MainThreadSampler:
    PERIOD_NS=20_000_000

    def __init__(self):
        main=threading.main_thread()
        self.ident,self.tid=main.ident,main.native_id
        self.cpu_clock=time.pthread_getcpuclockid(self.ident)
        self.proc=Path('/proc/self/task')/str(self.tid)
        self.proc_fds={};self.proc_open_errors={};self.proc_close_errors=[]
        for name in ('status','wchan','syscall','schedstat'):
            try:self.proc_fds[name]=os.open(self.proc/name,os.O_RDONLY|os.O_CLOEXEC)
            except OSError as error:
                self.proc_open_errors[name]=dict(valid=False,error=repr(error),errno=error.errno,read_attempted=False)
        self.rows=[];self.failure=None;self.collector_cpu_ns=None;self.stop_status=None
        self.skipped_periods=0
        self.identity=dict(pid=os.getpid(),main_ident=self.ident,main_native_tid=self.tid,
            period_ns=self.PERIOD_NS,main_cpu_clock_id=self.cpu_clock,
            python_switch_interval_s=sys.getswitchinterval(),
            semantics='Stack/proc/CPU reads are bracketed but non-atomic; proc syscall/GIL waits may include this observer')
        self.schedstats=self._read(Path('/proc/sys/kernel/sched_schedstats'))
        self.stop_event=threading.Event()
        self.thread=threading.Thread(target=self._run,name='net01d-main-observer',daemon=True)

    @staticmethod
    def _read(path,fd=None):
        before=time.monotonic_ns();cpu=time.thread_time_ns()
        try:
            raw=path.read_text() if fd is None else os.pread(fd,16384,0).decode(errors='replace')
            row=dict(valid=True,raw=raw.strip())
        except OSError as error:row=dict(valid=False,error=repr(error),errno=error.errno)
        row.update(read_begin_mono_ns=before,read_end_mono_ns=time.monotonic_ns(),
            reader_cpu_before_ns=cpu,reader_cpu_after_ns=time.thread_time_ns())
        return row

    def _sample(self,scheduled_mono_ns):
        start=time.monotonic_ns();cpu=time.thread_time_ns()
        main_cpu=time.clock_gettime_ns(self.cpu_clock)
        frame=sys._current_frames().get(self.ident)
        stack=[]
        while frame is not None:
            stack.append(dict(file=frame.f_code.co_filename,function=frame.f_code.co_name,line=frame.f_lineno))
            frame=frame.f_back
        row=dict(scheduled_mono_ns=scheduled_mono_ns,start_mono_ns=start,
            start_lateness_ns=start-scheduled_mono_ns,
            collector_cpu_start_ns=cpu,main_cpu_before_ns=main_cpu,
            stack_mono_ns=time.monotonic_ns(),stack=stack,stack_valid=bool(stack))
        proc={name:(self._read(self.proc/name,self.proc_fds[name]) if name in self.proc_fds
            else dict(self.proc_open_errors[name])) for name in ('status','wchan','syscall','schedstat')}
        status=proc['status']
        if status['valid']:
            fields=dict(line.split(':',1) for line in status['raw'].splitlines() if ':' in line)
            status.update(state=fields['State'].strip(),
                voluntary_ctxt_switches=int(fields['voluntary_ctxt_switches']),
                nonvoluntary_ctxt_switches=int(fields['nonvoluntary_ctxt_switches']))
            del status['raw']
        if proc['wchan']['valid']:
            proc['wchan']['symbol_available']=proc['wchan']['raw'] not in ('','0')
        sched=proc['schedstat']
        if sched['valid']:
            runtime,delay,slices=map(int,sched['raw'].split())
            sched.update(runtime_ns=runtime,run_delay_ns=delay,timeslices=slices,
                run_delay_interpretable=self.schedstats.get('valid') is True and self.schedstats['raw']=='1')
        row.update(proc=proc,main_cpu_after_ns=time.clock_gettime_ns(self.cpu_clock),
            end_mono_ns=time.monotonic_ns(),collector_cpu_end_ns=time.thread_time_ns())
        return row

    def _run(self):
        began=time.thread_time_ns()
        self.identity['collector_native_tid']=threading.get_native_id()
        deadline=time.monotonic_ns()+self.PERIOD_NS
        try:
            while not self.stop_event.wait(max(0.,(deadline-time.monotonic_ns())/1e9)):
                row=self._sample(deadline)
                deadline+=self.PERIOD_NS
                now=time.monotonic_ns()
                skipped=max(0,(now-deadline)//self.PERIOD_NS+1)
                row['skipped_periods_after']=skipped
                self.skipped_periods+=skipped
                self.rows.append(row)
                # Keep the fixed grid; skip missed ticks, never backfill stacks.
                deadline+=skipped*self.PERIOD_NS
        except Exception as error:
            self.failure=repr(error)
        finally:
            self._close_proc_fds()
            self.collector_cpu_ns=time.thread_time_ns()-began

    def _close_proc_fds(self):
        for name,fd in tuple(self.proc_fds.items()):
            try:os.close(fd)
            except OSError as error:self.proc_close_errors.append(dict(field=name,error=repr(error)))
            else:del self.proc_fds[name]
        if self.proc_close_errors and self.failure is None:
            self.failure='proc_fd_close_failed: '+repr(self.proc_close_errors)

    def start(self):
        self.identity['started_mono_ns']=time.monotonic_ns()
        try:self.thread.start()
        except Exception:
            self._close_proc_fds()
            raise

    def stop(self):
        before=time.monotonic_ns();self.stop_event.set();self.thread.join(timeout=1.)
        self.stop_status=dict(joined=not self.thread.is_alive(),failure=self.failure,
            stop_begin_mono_ns=before,stop_end_mono_ns=time.monotonic_ns(),
            collector_cpu_ns=self.collector_cpu_ns,samples=len(self.rows),
            skipped_periods=self.skipped_periods,proc_fds_remaining=len(self.proc_fds),
            proc_close_errors=list(self.proc_close_errors))
        return self.stop_status

    def snapshot(self):
        closed=self.stop_status is not None and self.stop_status['joined']
        return dict(identity=self.identity,kernel_sched_schedstats=self.schedstats,
            stop=self.stop_status,samples_unavailable=not closed,
            rows=self.rows if closed else None,
            limitations='No earliest DDS arrival or native C stack; Python caller only. GIL/proc snapshots perturb timing. Disabled/unavailable schedstats run_delay is not scheduling evidence.')
