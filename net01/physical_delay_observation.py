"""Bounded new-profile observations around unchanged original Guard decisions."""
from contextlib import contextmanager
from contextvars import ContextVar
import time

from delivery_guard import DeliveryGuard,frozen

_context=ContextVar('physical_guard_actual_predicate',default=None)
_state_fresh=frozen.state_fresh


def state_summary(state):
    if state is None:return None
    fields=('ready','generated_sim','sequence','odom_stamps','correction_stamps','failures','ages','localization_invalid')
    return {key:dict(state[key]) if isinstance(state.get(key),dict) else state.get(key) for key in fields}


def observed_state_fresh(state,now):
    value=_state_fresh(state,now)  # The actual original predicate, exactly once.
    context=_context.get()
    if context is not None and not value:
        guard=context['guard']
        source=('health' if state is guard.health else 'current_bound_mask'
            if guard.mask is not None and state is guard.mask['bound_state'] else 'incoming_bound_candidate')
        context['failed_calls'].append(dict(source=source,state=state_summary(state),
            actual_predicate_now_sim_s=now,actual_result=False,
            actual_limits=dict(ODOM_MAX_AGE=frozen.ODOM_MAX_AGE,
                CORRECTION_MAX_AGE=frozen.CORRECTION_MAX_AGE,
                CLOCK_QUANTUM=frozen.CLOCK_QUANTUM,CORRECTION_FUTURE=frozen.CORRECTION_FUTURE)))
    return value


class ObservedDeliveryGuard(DeliveryGuard):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.first_trip_observation=None
        self.last_blocked_arm_observation=None
        self.last_rejected_bound_candidate_observation=None

    @contextmanager
    def probe(self,operation):
        context=dict(guard=self,operation=operation,failed_calls=[])
        token=_context.set(context);previous=frozen.state_fresh
        frozen.state_fresh=observed_state_fresh
        try:yield context
        finally:
            frozen.state_fresh=previous
            _context.reset(token)

    def observation(self,context):
        control=self.control or {}
        return dict(operation=context['operation'],original_reason=context.get('reason'),
            failed_original_source_predicates=context['failed_calls'],
            actual_receipt_predicate_now_ns=context.get('receipt_predicate_now_ns'),
            actual_receipt_context=dict(health_receipt_sim_ns=self.health_receipt_sim_ns,
                mask_receipt_sim_ns=self.mask_receipt_sim_ns,
                health_receipt_limit_ns=self.health_receipt_limit_ns,
                mask_receipt_limit_ns=self.mask_receipt_limit_ns),
            health=state_summary(self.health),current_bound_mask=state_summary(
                None if self.mask is None else self.mask['bound_state']),
            latest_confirmed_physics_ACK=dict(
                physical_ns=control.get('last_successful_physics_ACK_physical_ns'),
                monotonic_ns=control.get('last_successful_physics_ACK_monotonic_ns')),
            observation_monotonic_ns=time.monotonic_ns())

    def reason(self,**kwargs):
        context=_context.get()
        if context is None or context['guard'] is not self:return super().reason(**kwargs)
        previous=self.sim_now_ns
        def observed_now():
            value=previous()  # Same actual clock call made by original reason.
            context['receipt_predicate_now_ns']=value
            return value
        if kwargs.get('receipt_sim_ns') is not None:
            context['receipt_predicate_now_ns']=kwargs['receipt_sim_ns']
        self.sim_now_ns=observed_now
        try:value=super().reason(**kwargs)
        finally:self.sim_now_ns=previous
        context['reason']=value
        return value

    def tick(self):
        if not self.armed or self.fault is not None:return super().tick()
        with self.probe('original_tick'):
            return super().tick()

    def trip(self,reason,**kwargs):
        first=self.fault is None;position=len(self.events);context=_context.get()
        value=super().trip(reason,**kwargs)
        if first:
            if context is None or context['guard'] is not self:
                context=dict(operation='original_trip_without_source_predicate',reason=reason,failed_calls=[])
            self.first_trip_observation=self.observation(context)
            self.events[position]['source_predicate_observation']=self.first_trip_observation
        return value

    def arm(self):
        with self.probe('original_arm') as context:
            value=super().arm()
            # Already faulted short-circuit performs no new reason/predicate;
            # do not overwrite a valid failure with an empty later observation.
            if not value and 'reason' in context:
                self.last_blocked_arm_observation=self.observation(context)
            return value

    def receive_bound(self,binding,native=None):
        with self.probe('original_receive_bound') as context:
            value=super().receive_bound(binding,native)
            if context['failed_calls']:
                self.last_rejected_bound_candidate_observation=self.observation(context)
            return value

    def bounded_observations(self):
        return dict(first_trip=self.first_trip_observation,last_blocked_arm=self.last_blocked_arm_observation,
            last_rejected_bound_candidate=self.last_rejected_bound_candidate_observation)
