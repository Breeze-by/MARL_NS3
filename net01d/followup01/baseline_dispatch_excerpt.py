# Exact inherited817 methods, saved read-only for before/after SDK comparison.
def record_cpu_span(table,key,wall,cpu,longspans=None,label=None):
    end=time.monotonic_ns();cpu_end=time.thread_time_ns()
    elapsed=end-wall;used=cpu_end-cpu
    if longspans is not None and elapsed>=10_000_000:
        longspans.append(dict(stage=label or key,begin_monotonic_ns=wall,end_monotonic_ns=end,
            begin_thread_cpu_ns=cpu,end_thread_cpu_ns=cpu_end))
    row=table.setdefault(key,dict(calls=0,wall_ns=0,thread_cpu_ns=0,max_wall_ns=0))
    row['calls']+=1;row['wall_ns']+=elapsed;row['thread_cpu_ns']+=used
    row['max_wall_ns']=max(row['max_wall_ns'],elapsed)

def drain_current_ready(executor,node,ready_set,after_handler=None,callback_limit=None,
                        profile=None,entity_label=None,longspans=None,side=None):
    """Bounded productive ready sets, in original SingleThreaded order.

    Keep the executor's cached iterator across cap hits. Do not wait/rebuild an
    empty waitset for every other-domain callback or favor any topic/timer.
    Timeout0 also ends a productive set; it does not mean readers are empty.
    """
    cap=callback_limit if callback_limit is not None else sum(
        len(tuple(getattr(node,name))) for name in
        ('subscriptions','timers','clients','services','guards','waitables'))
    completed=[]
    while len(completed)<cap:
        if profile is not None:wait_wall=time.monotonic_ns();wait_cpu=time.thread_time_ns()
        wait_kind='error'
        try:
            handler,entity,_=executor.wait_for_ready_callbacks(timeout_sec=0)
            wait_kind='ready'
        except TimeoutException:
            wait_kind='productive_set_end' if ready_set['productive'] else 'empty_set'
            if not ready_set['productive']:break
            ready_set['productive']=False
            continue
        except ShutdownException:
            wait_kind='shutdown'
            ready_set['shutdown']=True
            break
        finally:
            if profile is not None:record_cpu_span(profile['wait'],wait_kind,wait_wall,wait_cpu,
                    longspans,f'{side}:wait:{wait_kind}')
        began=time.monotonic()
        if profile is not None:handler_wall=time.monotonic_ns();handler_cpu=time.thread_time_ns()
        try:
            handler()
            if handler.exception() is not None:raise handler.exception()
            handler.result()
        finally:
            if profile is not None:record_cpu_span(profile['handlers'],entity_label(entity),handler_wall,handler_cpu,
                    longspans,f'{side}:handler:{entity_label(entity)}')
        completed.append((entity,began))
        ready_set['productive']=True
        if after_handler is not None:after_handler()
    return completed,cap

def _poll(self):
        now=time.monotonic()
        if self.last_poll is not None:self.dispatch_stats['max_poll_gap_wall_s']=max(
            self.dispatch_stats['max_poll_gap_wall_s'],now-self.last_poll)
        self.last_poll=now
        caps={side:sum(len(tuple(getattr(node,name))) for name in
            ('subscriptions','timers','clients','services','guards','waitables'))
            for side,node in zip(('C','R'),self.nodes)}
        used={side:0 for side in ('C','R')}
        spans={side:dict(wall=0.,cpu=0.) for side in ('C','R')}
        for state in self.ready_sets.values():state['shutdown']=False
        while True:
            productive=False
            for side,executor,node in zip(('C','R'),self.executors,self.nodes):
                if self.ready_sets[side]['shutdown']:continue
                before=time.monotonic();cpu=time.thread_time()
                if side=='C' and before<self.c_empty_until:
                    self.dispatch_stats['C']['empty_recheck_skips']+=1
                    continue
                completed,_=drain_current_ready(executor,node,self.ready_sets[side],
                    self.progress_transport,callback_limit=min(4,caps[side]-used[side]),
                    profile=None if self.cpu_profile is None else self.cpu_profile[side],
                    entity_label=self.profile_entity,longspans=self.profile_longspans,side=side)
                if side=='C':
                    if completed:self.c_empty_until=0.
                    elif not self.ready_sets[side]['shutdown']:
                        # Only an actually empty public query starts this fixed
                        # deadline; skipped probes never extend it. No sleep.
                        self.c_empty_until=time.monotonic()+.010
                        self.dispatch_stats['C']['empty_recheck_started']+=1
                spans[side]['wall']+=time.monotonic()-before
                spans[side]['cpu']+=time.thread_time()-cpu
                used[side]+=len(completed)
                productive=productive or bool(completed)
                for entity,began in completed:
                    for robot,guard in self.guards.items():
                        if entity is guard.timer:
                            timer=self.dispatch_stats['guard_timers'].setdefault(str(robot),dict(calls=0,max_gap_wall_s=0.,last=None))
                            if timer['last'] is not None:timer['max_gap_wall_s']=max(timer['max_gap_wall_s'],began-timer['last'])
                            timer['calls']+=1;timer['last']=began
            # Once an empty retry deadline is eligible, try that side again
            # after at most four other-side handlers.
            # Once either cap is used, defer all remaining work to the next poll.
            if not productive or any(used[side]>=caps[side] for side in ('C','R')):break
        for side in ('C','R'):
            stat=self.dispatch_stats[side];stat['batches']+=1;stat['callbacks']+=used[side]
            stat['cap_hits']+=int(used[side]==caps[side])
            stat['max_wall_s']=max(stat['max_wall_s'],spans[side]['wall'])
            stat['max_cpu_s']=max(stat['max_cpu_s'],spans[side]['cpu'])
        self.progress_transport()
