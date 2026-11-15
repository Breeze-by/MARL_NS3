"""Explicit A0: native clock/model control plus independent direct-ROS safety.

No business wire is installed. Apply the reviewed integration patch before
using this module: Gateway's default guardian/status/main hooks stay unchanged
for ordinary A1/B/C invocations. This file itself authorizes no execution.
"""
import json
import os
import time

from rclpy.qos import QoSProfile,DurabilityPolicy
from std_msgs.msg import String,UInt8MultiArray

from a0_runtime import A0LocalStop,SafetyRegistry
from bound_peer import decode_bound
from gateway import Gateway,main as gateway_main
from topic_wire import flows,qos as flow_qos


class DirectReferenceGateway(Gateway):
    def __init__(self,mode,socket,directory,session_id,**options):
        if mode!='A' or os.environ.get('NET01_DIRECT_REFERENCE')!='1':
            raise ValueError('A0 requires explicitly admitted mode A direct_reference')
        self.direct_health=[];self.direct_masks=[]
        self.final_registry=None
        super().__init__(mode,socket,directory,session_id,guardian_factory=A0LocalStop,**options)
        self.safety=SafetyRegistry(self.directory/'a0-safety.sock',session_id,self.guards)
        self.direct_subscriptions=[self.r.create_subscription(String,'/peer_keepout_state',
            self.receive_direct_health,flow_qos(flows(runtime=True)[31]))]
        qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.direct_subscriptions.extend(self.r.create_subscription(UInt8MultiArray,
            f'/net01/tb{robot}/peer_mask_bound',lambda message,r=robot:self.receive_direct_bound(r,message),qos)
            for robot in (1,2,3))
        self.record('a0_direct_reference_initialized',business_wires_installed=False,
            safety_socket=str(self.safety.path),safety_ack_wall_s=.1,
            retained_control='actual R clock/model -> native STEP/ACK; same physical coordinator/pacer',
            business='original ROS DDS in R92, original HQ directly addresses Nav2')

    def install_wires(self):
        # Base mode-A progression calls this only after actual hub/clock ready.
        # connected means control readiness here, never Wi-Fi qualification.
        self.record('a0_control_ready_no_business_wires')

    def send(self,*args,**kwargs):
        raise RuntimeError('Business send prohibited in A0 control-only Gateway')

    def receive(self,meta,body,rpc):
        raise RuntimeError('Unexpected business delivery in A0 control-only Gateway')

    def receive_direct_health(self,message):
        state=json.loads(message.data)
        for robot,stop in self.guards.items():
            before=time.monotonic_ns()
            accepted=stop.guard.receive_health(state)
            self.direct_health.append(dict(robot=robot,sequence=state['sequence'],
                state=state,accepted=accepted,before_monotonic_ns=before,
                after_monotonic_ns=time.monotonic_ns(),
                actual_receipt_monotonic_s=stop.guard.health_receipt,
                R_sim_ns=self.r.get_clock().now().nanoseconds,fault=stop.guard.fault))

    def receive_direct_bound(self,robot,message):
        before=time.monotonic_ns()
        binding,_=decode_bound(bytes(message.data),f'tb{robot}',self.session_id)
        validated=time.monotonic_ns()
        accepted=self.guards[robot].guard.receive_bound(binding)
        self.direct_masks.append(dict(robot=robot,binding=binding,accepted=accepted,
            validation_before_monotonic_ns=before,validation_after_monotonic_ns=validated,
            accept_after_monotonic_ns=time.monotonic_ns(),
            actual_receipt_monotonic_s=self.guards[robot].guard.mask_receipt,
            R_sim_ns=self.r.get_clock().now().nanoseconds))
        # Original BoundPeer already published its original mask to Nav2.
        # Validation is local safety observation; no duplicate mask publisher.

    def _progress_transport(self):
        self.safety.poll()
        super()._progress_transport()
        # A0 registry activity is not covered by A1/B epochs: keep legacy idle only.
        self._tail_empty_epoch={side:None for side in ('C','R')}

    def _export_controller_records(self):
        # Original Observer reads the original local journal in A0. No flow95,
        # second journal tail or controller-record republisher is needed here.
        return

    def extend_status(self,data):
        data['direct_reference']=True
        data['connection_semantics']='actual clock/native control ready; business uses direct R92 DDS'
        data['actual_rpc_cleanup'].update(
            A0_registered_owned_unknown_or_active=sum(len(stop.owned) for stop in self.guards.values()),
            A0_safety_connections=len(self.safety.connections))

    def _close(self):
        try:
            clean=super()._close()
        finally:
            # Base close may have pumped real late cleanup. Preserve that
            # actual final state before closing this owned listener.
            self.final_registry=self.safety.snapshot()
            self.safety.close()
        self.cleanup['a0_registered_owned_unknown_or_active']=self.final_registry['owned_unknown_or_active']
        self.cleanup['a0_safety_connections']=self.final_registry['connections']
        return clean and not any(self.final_registry['owned_unknown_or_active'].values()) and \
            not self.final_registry['connections'] and not any(stop.guard.fault for stop in self.guards.values())

    def persist(self):
        with (self.directory/'a0-direct-safety.json').open('x') as stream:
            json.dump(dict(direct_reference=True,business_wires_installed=self.wires is not None,
                registry=self.final_registry,health=self.direct_health,masks=self.direct_masks,
                policy_transport='original direct DDS; Unix is UUID safety registration/evidence only'),stream)
        with (self.directory/'a0-direct-safety-saved.json').open('x') as stream:
            json.dump(dict(saved=True,direct_reference=True,business_wires_installed=self.wires is not None,
                registered_owned_unknown_or_active=sum(len(owned) for owned in
                    self.final_registry['owned_unknown_or_active'].values()),
                safety_connections=self.final_registry['connections']),stream)
        super().persist()


if __name__=='__main__':
    raise SystemExit(gateway_main(gateway_factory=DirectReferenceGateway))
