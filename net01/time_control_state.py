"""Pure state for the explicit controlled-time profile, no ROS/model/clock I/O.

Physical end-time is a credit bound only. It is never a fabricated /clock or
ns3 STEP target. The native owner still advances only to actual observed clock.
"""
QUANTUM_NS=10_000_000
LOOKAHEAD_NS=2*QUANTUM_NS
TOKEN_WALL_PERIOD_NS=20_000_000  # Historical default .5RTF planned target.


class TimeControlState:
    def __init__(self,token_wall_period_ns=TOKEN_WALL_PERIOD_NS,progress_wall_timeout_ns=None):
        if token_wall_period_ns not in (20_000_000,10_000_000,40_000_000):
            raise ValueError('Unknown controlled-time planned wall period')
        self.token_wall_period_ns=token_wall_period_ns
        self.mode='RUN';self.failure=None;self.expected_shutdown=False;self.physics_failed=False
        self.native_ready=False;self.native_ns=0;self.anchor=None;self.clock_ns=None
        self.gateway_clock_ready=False
        self.physical_ns=None;self.iterations=None;self.inflight=False
        self.bootstrap_tokens=0;self.authority_exited=False
        self.next_wall_ns=None;self.last_planned_wall_ns=None;self.last_lateness_ns=0
        self.max_lateness_ns=0;self.late_tokens=0
        self.progress_wall_timeout_ns=progress_wall_timeout_ns
        self.progress_started_ns=None;self.clock_progress_ns=None;self.native_progress_ns=None
        self.inflight_since_ns=None;self.motion_armed_since_ns=None
        self.attempt_barrier=None;self.attempt_barrier_wait_ns=None
        self.attempt_barrier_pending=None
        self.startup_spawn_gate=None

    def configure_startup_spawn_gate(self,session_id,profile_id):
        self.startup_spawn_gate=dict(session_id=session_id,execution_profile=profile_id,ready=False)

    def startup_spawn_ready(self,row):
        gate=self.startup_spawn_gate
        if gate is None:return False,'startup_gate_not_enabled'
        if self.mode!='RUN' or self.authority_exited or self.expected_shutdown:
            return False,'not_running_authority'
        if row.get('session_id')!=gate['session_id']:return False,'wrong_session'
        if row.get('execution_profile')!=gate['execution_profile']:return False,'wrong_profile'
        if gate['ready']:return False,'duplicate_startup_ready'
        if self.physical_ns is not None or self.inflight or self.next_wall_ns is not None:
            return False,'physical_token_already_started'
        spawns=row.get('spawns',[])
        if (len(spawns)!=3 or {s.get('robot') for s in spawns}!={'tb1','tb2','tb3'}
                or any(s.get('returncode')!=0 or type(s.get('pid')) is not int or s['pid']<=0 for s in spawns)
                or len({s['pid'] for s in spawns})!=3):
            return False,'not_three_unique_actual_exit0'
        fence=row.get('factory_fence',{})
        if (fence.get('request')!='entity_info' or not fence.get('world_name')
                or fence.get('model_name')!='tb3' or fence.get('response_model_name')!='tb3'
                or fence.get('returncode')!=0 or type(fence.get('pid')) is not int or fence['pid']<=0):
            return False,'factory_cycle_fence_missing_or_failed'
        gate['ready']=True
        return True,'all_spawn_exit0_and_factory_cycle_fence_admitted'

    def configure_attempt_barrier(self,session_id,profile_id,contract):
        self.attempt_barrier=dict(session_id=session_id,execution_profile=profile_id,
            next_slot_ns=contract['first_decision_ns'],period_ns=contract['decision_period_ns'],
            end_ns=contract['decision_permission_end_ns'])

    def attempt_enter(self,row,now_ns):
        """Administrative release only; never clock/native progress or a token."""
        self.check_progress(now_ns)  # A late ACK cannot erase an expired wait.
        barrier=self.attempt_barrier
        if barrier is None:return False,'barrier_not_enabled'
        if self.mode!='RUN' or self.authority_exited or self.expected_shutdown:
            return False,'not_running_authority'
        if row.get('session_id')!=barrier['session_id']:return False,'wrong_session'
        if row.get('execution_profile')!=barrier['execution_profile']:return False,'wrong_profile'
        slot=barrier['next_slot_ns']
        if slot>=barrier['end_ns'] or row.get('planned_sim_ns')!=slot:
            return False,'not_current_planned_slot'
        if row.get('actual_sim_ns')!=slot:return False,'actual_clock_not_boundary'
        if self.inflight and self.physical_ns==slot-QUANTUM_NS:
            if self.attempt_barrier_pending is not None:return False,'duplicate_pending_entry'
            self.attempt_barrier_pending=dict(row)
            return False,'pending_actual_physics_ACK'
        if self.inflight or self.physical_ns!=slot:return False,'not_at_physical_boundary'
        barrier['next_slot_ns']+=barrier['period_ns']
        self.attempt_barrier_wait_ns=None
        self.attempt_barrier_pending=None
        return True,'current_boundary_released'

    def check_progress(self,now_ns):
        if self.progress_wall_timeout_ns is None:return None
        reason=None;physics=False
        if self.inflight and now_ns-self.inflight_since_ns>self.progress_wall_timeout_ns:
            reason='physics_RPC_wall_timeout';physics=True
        elif (self.mode=='RUN' and self.attempt_barrier_wait_ns is not None
                and now_ns-self.attempt_barrier_wait_ns>self.progress_wall_timeout_ns):
            reason='fixed_attempt_entry_ACK_wall_timeout'
        elif self.mode=='RUN' and self.motion_armed_since_ns is not None:
            clock_base=(self.motion_armed_since_ns if self.clock_progress_ns is None else
                max(self.motion_armed_since_ns,self.clock_progress_ns))
            native_base=(self.motion_armed_since_ns if self.native_progress_ns is None else
                max(self.motion_armed_since_ns,self.native_progress_ns))
            if now_ns-clock_base>self.progress_wall_timeout_ns:reason='actual_clock_progress_wall_timeout'
            elif now_ns-native_base>self.progress_wall_timeout_ns:reason='native_ACK_progress_wall_timeout'
        if reason:self.fail(reason,physics=physics)
        return reason


    def observe_motion_armed(self,now_ns):
        self.check_progress(now_ns)  # A repeated/late status cannot erase an expired interval.
        if self.progress_wall_timeout_ns is None or self.motion_armed_since_ns is not None:return False
        self.motion_armed_since_ns=now_ns
        return True

    def fail(self,reason,physics=False):
        if self.failure is None:self.failure=reason
        self.physics_failed=self.physics_failed or physics
        if self.physics_failed:self.mode='HOLD'
        elif self.mode in ('STOP_COUPLED','FAULT_STOP_OBSERVE') and self.authority_exited:
            self.mode='FAULT_STOP_OBSERVE'
        else:self.mode='HOLD'

    def clock(self,value,now_ns=None):
        if self.progress_wall_timeout_ns is not None:self.check_progress(now_ns)
        if self.clock_ns is not None and value<self.clock_ns:
            self.fail('actual_clock_rollback',physics=True);return
        if self.progress_wall_timeout_ns is not None and (self.clock_ns is None or value>self.clock_ns):self.clock_progress_ns=now_ns
        self.clock_ns=value

    def set_anchor(self,offset):
        if self.anchor is not None and self.anchor!=offset:
            self.fail('fixed_clock_anchor_changed');return
        self.anchor=offset

    def native(self,kind,value,now_ns=None):
        if self.progress_wall_timeout_ns is not None:self.check_progress(now_ns)
        if kind=='ready':
            self.native_ready=True
        elif kind=='step':
            if value<self.native_ns:self.fail('actual_native_ACK_rollback');return
            if self.progress_wall_timeout_ns is not None and value>self.native_ns:self.native_progress_ns=now_ns
            self.native_ns=value
        elif kind=='closed' and not self.expected_shutdown:
            self.fail('native_closed_before_expected_shutdown')

    def hold(self,expected_shutdown=False):
        self.mode='HOLD';self.expected_shutdown=self.expected_shutdown or expected_shutdown

    def run(self):
        if self.failure is not None or self.expected_shutdown:return False
        if self.mode!='RUN':
            self.next_wall_ns=None;self.progress_started_ns=None
        self.mode='RUN';self.authority_exited=False;return True

    def stop_observe(self,authority_exited):
        if not authority_exited or self.physics_failed or self.expected_shutdown:return False
        if self.mode=='HOLD':self.next_wall_ns=None
        self.authority_exited=True
        self.mode='FAULT_STOP_OBSERVE' if self.failure else 'STOP_COUPLED'
        return True

    def can_step(self,now_ns):
        if self.next_wall_ns is not None and now_ns<self.next_wall_ns:return False
        if self.inflight or self.physics_failed or self.expected_shutdown or self.mode=='HOLD':return False
        if self.mode=='FAULT_STOP_OBSERVE':return True
        if (self.mode=='RUN' and self.startup_spawn_gate is not None
                and not self.startup_spawn_gate['ready']):return False
        if (self.mode=='RUN' and self.attempt_barrier is not None
                and self.attempt_barrier['next_slot_ns']<self.attempt_barrier['end_ns']
                and self.physical_ns is not None
                and self.physical_ns>=self.attempt_barrier['next_slot_ns']):return False
        if not self.native_ready:return False
        if self.anchor is None:return self.gateway_clock_ready and self.bootstrap_tokens<2
        # Hub admits STEP only through its own known actual /clock horizon.
        # This independent best-effort reader is observation, not a second ACK:
        # a missing terminal sample must not deadlock physical credit.
        return (self.physical_ns is None or
            self.physical_ns+QUANTUM_NS<=self.anchor+self.native_ns+LOOKAHEAD_NS)

    def begin_step(self,now_ns):
        self.check_progress(now_ns)
        if not self.can_step(now_ns):raise RuntimeError('Unlicensed physical token')
        planned=now_ns if self.next_wall_ns is None else self.next_wall_ns
        self.last_planned_wall_ns=planned;self.last_lateness_ns=now_ns-planned
        self.max_lateness_ns=max(self.max_lateness_ns,self.last_lateness_ns)
        self.late_tokens+=int(self.last_lateness_ns>0)
        self.next_wall_ns=planned+self.token_wall_period_ns
        self.inflight=True
        if self.progress_wall_timeout_ns is not None:
            self.inflight_since_ns=now_ns
            if self.progress_started_ns is None:
                self.progress_started_ns=now_ns  # Token telemetry only, not an actual clock/native ACK.

    def complete_step(self,response,now_ns=None):
        if self.progress_wall_timeout_ns is not None:self.check_progress(now_ns)
        if not self.inflight:raise RuntimeError('No physical token outstanding')
        self.inflight=False;self.inflight_since_ns=None
        before,after=response['before_ns'],response['after_ns']
        ib,ia=response['before_iterations'],response['after_iterations']
        if (after-before!=QUANTUM_NS or ia-ib!=10 or response['completed_steps']!=10
            or (self.physical_ns is not None and before!=self.physical_ns)
            or (self.iterations is not None and ib!=self.iterations)):
            self.fail('post_physics_token_mismatch',physics=True);return
        self.physical_ns=after;self.iterations=ia
        if (self.mode=='RUN' and self.attempt_barrier is not None
                and self.attempt_barrier['next_slot_ns']<self.attempt_barrier['end_ns']
                and after>=self.attempt_barrier['next_slot_ns']):
            if after!=self.attempt_barrier['next_slot_ns']:
                self.fail('physical_attempt_boundary_crossed',physics=True)
            else:self.attempt_barrier_wait_ns=now_ns
        if self.anchor is None:self.bootstrap_tokens+=1
