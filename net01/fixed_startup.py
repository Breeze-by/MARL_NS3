"""Explicit absolute-sim decision permission; frozen allocation stays unchanged."""
import json
import os
from pathlib import Path
import socket
import time


class FixedStartupGate:
    def __init__(self, node, profile):
        self.node=node
        self.profile=profile['id']
        self.contract=profile['startup_contract']
        self.next_slot=self.contract['first_decision_ns']
        self.rows=[];self.submissions=[];self.original_send_goal=node.send_goal;self.failure=None;self.finished=False;self.permission_closed=False
        self.directory=Path(node.events.name).parent
        self.attempt_ack_socket=None
        if profile.get('attempt_entry_barrier',{}).get('id')=='physical-boundary-attempt-enter-v1':
            self.attempt_ack_address=str(Path(os.environ['NET01_TIME_CONTROL_DIRECTORY'])/'ack.sock')
            self.attempt_ack_session=int(os.environ['NET01_SESSION_ID'])
            self.attempt_ack_socket=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
            self.attempt_ack_socket.setblocking(False)

    def tick(self):
        actual=self.node.get_clock().now().nanoseconds
        if actual>=self.contract['decision_permission_end_ns'] and self.next_slot>=self.contract['decision_permission_end_ns']:
            if not self.permission_closed:
                self.permission_closed=True
                self.rows.append(dict(kind='decision_permission_closed',actual_sim_ns=actual,
                    planned_sim_ns=self.contract['decision_permission_end_ns'],monotonic_ns=time.monotonic_ns(),realtime_ns=time.time_ns()))
                self.timer.cancel()
            return
        if actual<self.next_slot or self.failure is not None:return
        row=dict(kind='decision_attempt',planned_sim_ns=self.next_slot,actual_sim_ns=actual,
            monotonic_ns=time.monotonic_ns(),realtime_ns=time.time_ns(),lateness_ns=actual-self.next_slot)
        self.rows.append(row)
        if row['lateness_ns']>self.contract['timing_tolerance_ns']:
            self.failure='fixed decision slot missed'
            row['attempted']=False
            self.timer.cancel()
            self.node.worker_error=self.failure
            self.node.halt('fixed_startup_timing_error')
            self.node.context.try_shutdown()
            return
        if self.attempt_ack_socket is not None:
            ack=dict(kind='hq_attempt_enter',session_id=self.attempt_ack_session,
                execution_profile=self.profile,planned_sim_ns=self.next_slot,
                actual_sim_ns=actual,monotonic_ns=time.monotonic_ns(),realtime_ns=time.time_ns())
            row['attempt_enter_ACK']=ack
            row['attempted']=False
            self.attempt_ack_socket.sendto(json.dumps(ack).encode(),self.attempt_ack_address)
            row['attempt_enter_ACK_sent_monotonic_ns']=time.monotonic_ns()
        self.next_slot+=self.contract['decision_period_ns']
        row['attempted']=True
        # Missing observations / policy WAIT are original allocator outcomes.
        # This must call the original gate even when no NN inference follows.
        self.node.decision_callback()
        row['callback_return_monotonic_ns']=time.monotonic_ns()
        row['callback_return_realtime_ns']=time.time_ns()
        row['callback_return_sim_ns']=self.node.get_clock().now().nanoseconds

    def submit(self, robot, target, token):
        actual=self.node.get_clock().now().nanoseconds
        admitted=self.contract['first_decision_ns']<=actual<self.contract['decision_permission_end_ns']
        row=dict(kind='goal_submission_permission',robot=robot,target=list(target),token=token,
            actual_sim_ns=actual,monotonic_ns=time.monotonic_ns(),realtime_ns=time.time_ns(),
            admitted=admitted,permission_basis='entry_to_original_send_goal_not_DDS_send_or_acceptance')
        self.submissions.append(row)
        if not admitted:
            row['outcome']='NOT_SUBMITTED_OUTSIDE_DECLARED_BUDGET'
            row['synthetic_Action_response']=False
            return
        try:
            return self.original_send_goal(robot,target,token)
        finally:
            row['original_return_or_unwind_monotonic_ns']=time.monotonic_ns()
            row['original_return_or_unwind_realtime_ns']=time.time_ns()
            row['original_return_or_unwind_sim_ns']=self.node.get_clock().now().nanoseconds

    def finish(self):
        if self.finished:return
        self.finished=True
        if self.attempt_ack_socket is not None:self.attempt_ack_socket.close()
        (self.directory/'startup_gate.json').write_text(json.dumps(dict(
            profile=self.profile,contract=self.contract,failure=self.failure,events=self.rows,goal_submissions=self.submissions,
            scope='actual callbacks; first ATTEMPT is not a requirement for NN inference; permission end is not task completion'),indent=2)+'\n')


def install_startup_gate(node, profile):
    gate=FixedStartupGate(node,profile)
    node.timer.cancel()  # Constructor timer has not yet been spun.
    gate.timer=node.create_timer(profile['native_step_quantum_ns']/1e9,gate.tick)
    node._fixed_startup_gate=gate
    node.send_goal=gate.submit
    node.record(dict(kind='fixed_startup_initialized',sim=node.now(),profile=profile['id'],
        contract=gate.contract['id'],planned_autonomy_sim_ns=gate.contract['autonomy_epoch_ns'],
        planned_first_attempt_sim_ns=gate.next_slot,
        planned_permission_end_sim_ns=gate.contract['decision_permission_end_ns']))
    return gate
