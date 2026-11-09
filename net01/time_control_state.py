"""Pure state for the explicit controlled-time profile, no ROS/model/clock I/O.

Physical end-time is a credit bound only. It is never a fabricated /clock or
ns3 STEP target. The native owner still advances only to actual observed clock.
"""
QUANTUM_NS=10_000_000
LOOKAHEAD_NS=2*QUANTUM_NS


class TimeControlState:
    def __init__(self):
        self.mode='RUN';self.failure=None;self.expected_shutdown=False;self.physics_failed=False
        self.native_ready=False;self.native_ns=0;self.anchor=None;self.clock_ns=None
        self.physical_ns=None;self.iterations=None;self.inflight=False
        self.bootstrap_tokens=0;self.authority_exited=False

    def fail(self,reason,physics=False):
        if self.failure is None:self.failure=reason
        self.physics_failed=self.physics_failed or physics
        if self.physics_failed:self.mode='HOLD'
        elif self.mode in ('STOP_COUPLED','FAULT_STOP_OBSERVE') and self.authority_exited:
            self.mode='FAULT_STOP_OBSERVE'
        else:self.mode='HOLD'

    def clock(self,value):
        if self.clock_ns is not None and value<self.clock_ns:
            self.fail('actual_clock_rollback',physics=True);return
        self.clock_ns=value

    def set_anchor(self,offset):
        if self.anchor is not None and self.anchor!=offset:
            self.fail('fixed_clock_anchor_changed');return
        self.anchor=offset

    def native(self,kind,value):
        if kind=='ready':
            self.native_ready=True
        elif kind=='step':
            if value<self.native_ns:self.fail('actual_native_ACK_rollback');return
            self.native_ns=value
        elif kind=='closed' and not self.expected_shutdown:
            self.fail('native_closed_before_expected_shutdown')

    def hold(self,expected_shutdown=False):
        self.mode='HOLD';self.expected_shutdown=self.expected_shutdown or expected_shutdown

    def run(self):
        if self.failure is not None or self.expected_shutdown:return False
        self.mode='RUN';self.authority_exited=False;return True

    def stop_observe(self,authority_exited):
        if not authority_exited or self.physics_failed or self.expected_shutdown:return False
        self.authority_exited=True
        self.mode='FAULT_STOP_OBSERVE' if self.failure else 'STOP_COUPLED'
        return True

    def can_step(self):
        if self.inflight or self.physics_failed or self.expected_shutdown or self.mode=='HOLD':return False
        if self.mode=='FAULT_STOP_OBSERVE':return True
        if not self.native_ready:return False
        if self.anchor is None:return self.bootstrap_tokens<2
        if self.clock_ns is None or self.anchor+self.native_ns>self.clock_ns:
            return False  # Observe the real sample, never manufacture one.
        return (self.physical_ns is None or
            self.physical_ns+QUANTUM_NS<=self.anchor+self.native_ns+LOOKAHEAD_NS)

    def begin_step(self):
        if not self.can_step():raise RuntimeError('Unlicensed physical token')
        self.inflight=True

    def complete_step(self,response):
        if not self.inflight:raise RuntimeError('No physical token outstanding')
        self.inflight=False
        before,after=response['before_ns'],response['after_ns']
        ib,ia=response['before_iterations'],response['after_iterations']
        if (after-before!=QUANTUM_NS or ia-ib!=10 or response['completed_steps']!=10
            or (self.physical_ns is not None and before!=self.physical_ns)
            or (self.iterations is not None and ib!=self.iterations)):
            self.fail('post_physics_token_mismatch',physics=True);return
        self.physical_ns=after;self.iterations=ia
        if self.anchor is None:self.bootstrap_tokens+=1
