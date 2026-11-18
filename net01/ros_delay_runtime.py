"""Opt-in source-age globals and one reliable, constant-wall-delay FIFO."""
from collections import deque
import os
import time

from execution_profile import ROS_DELAY_PROFILE_ID,PHYSICS_DELAY_PROFILE_ID,DELAY_FRESHNESS_PROFILE_IDS


def install_source_freshness(profile, owner):
    if profile is None or profile['id'] not in DELAY_FRESHNESS_PROFILE_IDS:
        return None
    import peer_keepout
    import business_peer
    policy = profile['source_freshness']
    expected_policy=('physics-delay-source-age-v1' if profile['id']==PHYSICS_DELAY_PROFILE_ID else 'ros-delay-source-age-v1')
    if policy['id'] != expected_policy:
        raise ValueError('Unknown source-age contract')
    names = ('ODOM_MAX_AGE', 'CORRECTION_MAX_AGE')
    before = {module.__name__: {name: getattr(module, name) for name in names}
        for module in (peer_keepout, business_peer)}
    for module in (peer_keepout, business_peer):
        module.ODOM_MAX_AGE = policy['odom_max_age_sim_s']
        module.CORRECTION_MAX_AGE = policy['correction_max_age_sim_s']
    receipt = profile.get('receipt_freshness')
    receipt_proof = None
    if receipt is not None:
        receipt_before = {module.__name__: module.ODOM_RECEIPT_MAX_AGE
            for module in (peer_keepout, business_peer)}
        for module in (peer_keepout, business_peer):
            module.ODOM_RECEIPT_MAX_AGE = receipt['projected_odom_max_age_sim_s']
        receipt_proof = dict(policy=receipt, before=receipt_before,
            module_projected_odom_receipt_s={module.__name__: module.ODOM_RECEIPT_MAX_AGE
                for module in (peer_keepout, business_peer)},
            producer_function_copied_binding=business_peer.BusinessPeer.publish_masks.__globals__['ODOM_RECEIPT_MAX_AGE'],
            applicable_instance_limits={})
    return dict(owner=owner, pid=os.getpid(), execution_profile=profile['id'], policy=policy,
        monotonic_ns=time.monotonic_ns(), before=before,
        applied={module.__name__: {name: getattr(module, name) for name in names}
            for module in (peer_keepout, business_peer)},
        state_fresh_uses_peer_module_globals=peer_keepout.state_fresh.__globals__ is peer_keepout.__dict__,
        scope='Process-local globals before Node construction; original functions, timestamps and other gates unchanged',
        **({'receipt_freshness_applied':receipt_proof} if receipt_proof is not None else {}))


def poststop_physical_closure(observer, controller_exited):
    """Persistence permission only; never repair the original run/seal result."""
    last = observer.last_stop_result or {}
    evidence = last.get('observed_stop') or {}
    ownership = evidence.get('request_ownership', {})
    return (controller_exited and observer.authority_stopped and last.get('stage') == 'final'
        and last.get('success') is True and evidence.get('authority_stopped') is True
        and evidence.get('ownership_closed') is True and ownership.get('closed') is True
        and evidence.get('lifecycle_pause_healthy') is True and evidence.get('rpc_errors') == []
        and observer.paused_robots == {'tb1', 'tb2', 'tb3'})


class WallDelayFIFO:
    def __init__(self, milliseconds):
        if type(milliseconds) is not int or milliseconds not in (0, 100, 200, 300, 400, 500):
            raise ValueError('Declared one-way wall delay must be D0..D500')
        self.delay_ns = milliseconds * 1_000_000
        self.pending = deque()
        self.rows = []

    def admit(self, frame, capture_ns, sim_ns):
        meta, body, rpc = frame
        row = dict(sequence=meta['native_id'], sender=meta['sender'], receiver=meta['receiver'],
            flow=meta['flow'], rpc_id=rpc, bytes=len(body), capture_monotonic_ns=capture_ns,
            capture_sim_ns=sim_ns, due_monotonic_ns=capture_ns+self.delay_ns,
            release_monotonic_ns=None)
        self.rows.append(row)
        self.pending.append((frame, row))

    def release_due(self, now_ns, sim_ns=None, phase='open_ingress'):
        ready = []
        while self.pending and self.pending[0][1]['due_monotonic_ns'] <= now_ns:
            frame, row = self.pending.popleft()
            row.update(release_monotonic_ns=now_ns,
                release_sim_ns=sim_ns,
                release_phase=phase,
                injected_hold_ns=now_ns-row['capture_monotonic_ns'],
                release_overshoot_ns=now_ns-row['due_monotonic_ns'])
            ready.append(frame)
        return ready

    def pending_rpc(self):
        return sum(200 <= row['flow'] < 300 and (row['flow']-200)%20 <= 5
            for _, row in self.pending)
