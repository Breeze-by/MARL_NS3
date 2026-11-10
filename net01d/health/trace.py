"""Opt-in, single-caller RAM observations; no parsing, I/O or control decisions.

The owner constructs this only when diagnostics are enabled. Caller-supplied
simulation times retain their own named bases; only mono_ns is cross-process
elapsed time on the same host. thread_cpu_ns is comparable within this thread.
"""
import os
import threading
import time


class HealthTrace:
    def __init__(self):
        self.identity = dict(pid=os.getpid(), native_thread_id=threading.get_native_id(),
            mono_clock='time.monotonic_ns, same host',
            cpu_clock='time.thread_time_ns, owning thread only')
        self.rows = []

    def stamp(self, stage, sequence=None, flow=None, **fields):
        mono = time.monotonic_ns()
        cpu = time.thread_time_ns()
        row = dict(stage=stage, sequence=sequence, flow=flow, **fields)
        row.update(mono_ns=mono, thread_cpu_ns=cpu)
        self.rows.append(row)
        return row

    def snapshot(self):
        return dict(identity=self.identity, rows=self.rows)
