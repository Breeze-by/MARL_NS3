"""No-Node check of the two actual metadata wrappers' call/exception semantics."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from topic_wire import TopicWire,flows
from bound_peer import BoundPeer,frozen
from tf2_msgs.msg import TFMessage
from geometry_msgs.msg import TransformStamped


def main():
    checks={};message=TFMessage()
    for frame,child,sec,nano in [('map','odom',41,123456789),('odom','base_footprint',42,7654321)]:
        t=TransformStamped();t.header.frame_id=frame;t.child_frame_id=child
        t.header.stamp.sec=sec;t.header.stamp.nanosec=nano;t.transform.rotation.w=1.
        message.transforms.append(t)
    original=copy.deepcopy(message)
    clock=SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=42_100_000_000))
    node=SimpleNamespace(get_clock=lambda:clock)
    sent=[]
    source=TopicWire.__new__(TopicWire)
    source.node=node;source.side='R';source.specs=flows();source.captured=[]
    source.send=lambda *args:sent.append(args)
    source.capture(23,message)
    checks['source_original_fields_immutable']=message==original
    checks['source_exactly_one_original_send']=len(sent)==1 and sent[0][0:3]==(1,0,23)
    checks['source_records_each_original_edge_header']=source.captured[0]['tf_edges']==[
        dict(frame_id='map',child_frame_id='odom',stamp_ns=41_123_456_789),
        dict(frame_id='odom',child_frame_id='base_footprint',stamp_ns=42_007_654_321)]
    checks['source_capture_nodesim_from_actual_clock']=source.captured[0]['capture_node_sim_ns']==42_100_000_000
    published=[];publisher=SimpleNamespace(publish=lambda m:published.append(copy.deepcopy(m)))
    target=TopicWire.__new__(TopicWire)
    target.node=node;target.specs=flows();target.publishers={23:publisher};target.delivered=[]
    meta=dict(flow=23,sender=1,receiver=0)
    target.receive(meta,sent[0][3],0)
    row=target.delivered[-1]
    checks['destination_publish_once_all_fields_unchanged']=published==[original]
    checks['destination_times_bracket_actual_publisher_call']=row['publisher_returned'] and row['publish_after_monotonic_ns']>=row['endpoint_publish_monotonic_ns'] and row['publish_after_thread_cpu_ns']>=row['publish_before_thread_cpu_ns']
    checks['same_captured_body_hash_not_second_serializer']=row['cdr_sha256']==source.captured[0]['cdr_sha256']
    failure=RuntimeError('controlled publisher exception');calls=[]
    def fail(m):calls.append(m);raise failure
    publisher.publish=fail
    try:target.receive(meta,sent[0][3],0)
    except RuntimeError as error:checks['publisher_exception_identity_preserved']=error is failure
    checks['publisher_exception_still_recorded_once']=len(calls)==1 and not target.delivered[-1]['publisher_returned'] and 'publish_after_monotonic_ns' in target.delivered[-1]

    peer=BoundPeer.__new__(BoundPeer);peer.tf_input_records=[];peer.correction_stamps={'tb1':40.}
    peer.get_clock=lambda:clock
    parent=frozen.PeerKeepout.receive_tf;calls=[];token=object()
    def parent_call(self,m,robot,static):
        calls.append((m,robot,static));self.correction_stamps[robot]=41.123456789
        return token
    try:
        frozen.PeerKeepout.receive_tf=parent_call
        result=peer.receive_tf(message,'tb1',False)
        checks['peer_original_called_once_same_input_and_return']=len(calls)==1 and calls[0][0] is message and calls[0][1:]==('tb1',False) and result is token
        checks['peer_original_input_fields_unchanged']=message==original
        checks['peer_held_header_before_after_observed']=peer.tf_input_records[-1]['held_correction_stamp_before']==40. and peer.tf_input_records[-1]['held_correction_stamp_after']==41.123456789
        def parent_fail(self,m,robot,static):
            calls.append((m,robot,static));raise failure
        frozen.PeerKeepout.receive_tf=parent_fail
        try:peer.receive_tf(message,'tb1',False)
        except RuntimeError as error:checks['peer_exception_identity_preserved']=error is failure
        checks['peer_exception_one_call_and_final_metadata']=len(calls)==2 and len(peer.tf_input_records)==2 and not peer.tf_input_records[-1]['original_returned'] and 'after_monotonic_ns' in peer.tf_input_records[-1]
    finally:frozen.PeerKeepout.receive_tf=parent
    result=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,
        scope='Actual wrapper methods with value-only typed TF and controlled original-call substitutes; no Buffer semantics or runtime latency claim',
        ROS_Node=0,Gazebo=0,NN=0)
    with Path(__file__).with_name('tf-metadata-direct-check-01.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result),flush=True)
    return 0 if all(checks.values()) else 1


if __name__=='__main__':raise SystemExit(main())
