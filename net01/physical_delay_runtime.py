"""Opt-in reliable FIFO timed by real completed physical Step ACKs only."""
from collections import deque


class PhysicalDelayFIFO:
    def __init__(self, delay_ns, session_id, profile_id, activation_ns=20_000_000_000):
        if delay_ns not in (0,500_000_000):
            raise ValueError('Physical delay is explicitly D0 or P500')
        self.delay_ns=delay_ns;self.session_id=session_id;self.profile_id=profile_id
        self.activation_ns=activation_ns
        self.pending=deque();self.unanchored=deque();self.rows=[]
        self.ACK_monotonic_ns=self.physical_ns=None
        self.clock_rejections=0

    def admit(self,frame,capture_ns,local_sim_ns):
        meta,body,rpc=frame
        row=dict(sequence=meta['native_id'],sender=meta['sender'],receiver=meta['receiver'],
            flow=meta['flow'],rpc_id=rpc,bytes=len(body),capture_monotonic_ns=capture_ns,
            capture_local_R_clock_ns=local_sim_ns,anchor_physical_ns=None,anchor_ACK_monotonic_ns=None,
            anchor_received_monotonic_ns=None,due_physical_ns=None,release_physical_ns=None,
            release_monotonic_ns=None)
        self.rows.append(row);self.pending.append((frame,row));self.unanchored.append(row)

    def observe_ACK(self,state,received_monotonic_ns):
        if state['session_id']!=self.session_id or state['execution_profile']!=self.profile_id:
            self.clock_rejections+=1;return
        mono=state['last_successful_physics_ACK_monotonic_ns']
        physical=state['last_successful_physics_ACK_physical_ns']
        if mono is None and physical is None:return  # No actual completed Step yet.
        if type(mono) is not int or type(physical) is not int:
            raise ValueError('Incomplete actual physical ACK identity')
        if self.ACK_monotonic_ns is not None and mono<=self.ACK_monotonic_ns:
            return
        if self.physical_ns is not None and physical<self.physical_ns:
            raise ValueError('Actual physical ACK rollback')
        self.ACK_monotonic_ns=mono;self.physical_ns=physical
        # Anchor ALL newly eligible admissions independently of older due times;
        # otherwise a head waiting500ms would incorrectly serialize later holds.
        while self.unanchored and self.unanchored[0]['capture_monotonic_ns']<=mono:
            row=self.unanchored.popleft()
            delay=self.delay_ns if physical>=self.activation_ns else 0
            row.update(anchor_physical_ns=physical,anchor_ACK_monotonic_ns=mono,
                anchor_received_monotonic_ns=received_monotonic_ns,
                applied_delay_ns=delay,due_physical_ns=physical+delay,
                treatment_active=physical>=self.activation_ns)

    def release_due(self,now_ns,phase):
        frames=[]
        while self.pending:
            frame,row=self.pending[0]
            due=row['due_physical_ns']
            if due is None or self.physical_ns<due:break
            self.pending.popleft()
            row.update(release_monotonic_ns=now_ns,release_physical_ns=self.physical_ns,
                release_ACK_monotonic_ns=self.ACK_monotonic_ns,release_phase=phase,
                anchor_to_release_physical_ns=self.physical_ns-row['anchor_physical_ns'],
                release_overshoot_physical_ns=self.physical_ns-due,
                capture_to_release_wall_ns=now_ns-row['capture_monotonic_ns'])
            frames.append(frame)
        return frames

    def pending_rpc(self):
        return sum(200<=row['flow']<300 and (row['flow']-200)%20<=5 for _,row in self.pending)
