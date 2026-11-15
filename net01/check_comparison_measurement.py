"""Actual lightweight DDS + unchanged IPC frame qualification, no simulation."""
import argparse
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'net01e/followup01')]


def check():
    import rclpy
    from rclpy.context import Context
    from rclpy.node import Node
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.signals import SignalHandlerOptions
    from nav_msgs.msg import Odometry
    from comparison_measurement import install_take_trace,install_gateway_takes,ComparisonHubClient,_context
    from comparison_topic_wire import ComparisonTopicWire
    from hub_client import HubClient
    contexts=[];nodes=[];executors=[]
    def domain(number):
        context=Context();rclpy.init(context=context,domain_id=number,signal_handler_options=SignalHandlerOptions.NO)
        contexts.append(context);executor=SingleThreadedExecutor(context=context);executors.append(executor)
        return context,executor
    def node(name,context,executor):
        value=Node(name,context=context);nodes.append(value);executor.add_node(value);return value
    cr,er=domain(97);cc,ec=domain(98)
    source=node('measurement_source',cr,er);observer=node('measurement_observer',cr,er)
    gateway_r=node('measurement_wire_r',cr,er);gateway_c=node('measurement_wire_c',cc,ec)
    direct=node('measurement_direct_hq',cr,er);transported=node('measurement_transport_hq',cc,ec)
    received_source=[];received_direct=[];received_transport=[]
    observer.create_subscription(Odometry,'/tb1/odom',received_source.append,10)
    direct.create_subscription(Odometry,'/tb1/odom',received_direct.append,10)
    transported.create_subscription(Odometry,'/tb1/odom',received_transport.append,10)
    traces={n:install_take_trace(n,e,retain_pending=True) for n,e in
        ((observer,er),(direct,er),(transported,ec))}
    wc=ComparisonTopicWire(gateway_c,'C',lambda *a:None,bound_masks=True,runtime=True)
    frames=[]
    def forward(sender,receiver,flow,body,rpc,stamp):
        frames.append((flow,body))
        wc.receive(dict(sender=sender,receiver=receiver,flow=flow,message_id=len(frames)),body,rpc)
    wr=ComparisonTopicWire(gateway_r,'R',forward,bound_masks=True,runtime=True)
    safety=[]
    gateway_r.create_subscription(Odometry,'/tb1/odom',safety.append,10)
    install_gateway_takes(SimpleNamespace(nodes=[gateway_r,gateway_c],executors=[er,ec],wires={'R':wr,'C':wc}))
    pub=source.create_publisher(Odometry,'/tb1/odom',10)
    deadline=time.monotonic()+7
    def until(predicate):
        while not predicate():
            if time.monotonic()>deadline:raise TimeoutError('Bounded comparison DDS fixture')
            er.spin_once(timeout_sec=.001);ec.spin_once(timeout_sec=.001)
    try:
        until(lambda:pub.get_subscription_count()==4 and wc.publishers[22].get_subscription_count()==1)
        for count in (1,2):
            pub.publish(Odometry())  # Equal bodies, distinct actual publications.
            until(lambda:len(received_source)==len(received_direct)==len(received_transport)==len(safety)==count)
        assert len(wr.captured)==len(wc.delivered)==2
        assert len(gateway_r._comparison_take_trace.rows)==2 and not gateway_r._comparison_take_trace.pending
        source_stamps=[row['metadata']['source_timestamp'] for row in traces[observer].rows]
        assert source_stamps==[row['metadata']['source_timestamp'] for row in traces[direct].rows]
        assert source_stamps==[row['source_take']['metadata']['source_timestamp'] for row in wr.captured]
        assert source_stamps[0]!=source_stamps[1]
        assert wr.captured[0]['cdr_sha256']==wr.captured[1]['cdr_sha256']
        assert [row['capture_seq'] for row in wr.captured]==[1,2]
        assert len(traces[observer].rows)==len(received_source)==2
        for trace,messages in ((traces[observer],received_source),(traces[direct],received_direct),
                               (traces[transported],received_transport)):
            assert all((row['topic'],id(message)) in trace.pending for row,message in zip(trace.rows,messages))
        assert [row['metadata']['source_timestamp'] for row in traces[transported].rows]!=source_stamps
        # The same original HubClient.frame, same arguments and bytes; no socket.
        baseline=HubClient.__new__(HubClient);baseline.outgoing=bytearray();baseline.control_trace=None
        measured=ComparisonHubClient.__new__(ComparisonHubClient);measured.outgoing=bytearray();measured.control_trace=None
        measured.comparison_send_seq=0;measured.comparison_sends=[]
        for ordinal,flow in ((1,900),(2,22),(3,22)):
            meta=dict(kind='send',sender=1,receiver=0,flow=flow,source_stamp_ns=0)
            body=b'unchanged-full-rpc-prefix-and-CDR';capture={}
            _context.capture=None if ordinal==1 else capture
            baseline.frame(meta,body);measured.frame(meta,body)
            if ordinal>1:assert capture['hub_send_seq']==ordinal
        _context.capture=None
        assert measured.outgoing==baseline.outgoing and measured.comparison_send_seq==3
        assert [row['send_seq'] for row in measured.comparison_sends]==[2,3]
        return dict(status='PASS',actual_dds=True,source_callback_and_same_native_take_objects=True,
            direct_original_source_timestamps_match=True,transported_source_recovered_from_original_take=True,
            equal_bodies_not_used_as_unique_ids=True,republished_timestamp_differs_and_is_not_original_source=True,
            original_ipc_bytes_unchanged=True,send_ordinal_includes_handshake=True,
            same_topic_safety_subscription_excluded_from_wire_pending=True,
            no_nn_no_gazebo_no_ns3=True,source_timestamps=source_stamps)
    finally:
        for executor in executors:executor.shutdown(timeout_sec=0)
        for value in nodes:value.destroy_node()
        for context in contexts:context.shutdown()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    result=check();(args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
