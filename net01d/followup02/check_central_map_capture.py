"""One isolated passive-capture check: real ROS CDR, no init/Node/ROS graph."""
import argparse
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from nav_msgs.msg import OccupancyGrid
from rclpy.serialization import deserialize_message

from gateway import Gateway
import topic_wire
from topic_wire import TopicWire


class NodeDouble:
    def __init__(self):
        self.subscriptions=[];self.publishers=[];self.published=[]

    def create_subscription(self,cls,topic,callback,qos):
        self.subscriptions.append((cls,topic,qos.depth,qos.durability))
        return callback

    def create_publisher(self,cls,topic,qos):
        self.publishers.append((cls,topic,qos.depth,qos.durability))
        return SimpleNamespace(publish=self.published.append)

    def get_clock(self):
        return SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=9_000_000_000))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args()
    args.directory.mkdir(parents=True,exist_ok=False)
    gateway=Gateway.__new__(Gateway)  # Never construct ROS contexts or Nodes.
    gateway.directory=args.directory;gateway.gz=8_900_000_000
    gateway.central_map_captures=[]
    sent=[];off_node=NodeDouble();on_node=NodeDouble();r_node=NodeDouble()
    off=TopicWire(off_node,'C',lambda *args:sent.append(args),runtime=True)
    on=TopicWire(on_node,'C',lambda *args:sent.append(args),runtime=True,
        central_map_capture=gateway.retain_central_map)
    r=TopicWire(r_node,'R',lambda *args:sent.append(args),runtime=True,
        central_map_capture=gateway.retain_central_map)
    message=OccupancyGrid()
    message.header.frame_id='merge_map';message.header.stamp.sec=2
    message.info.width=2;message.info.height=1;message.info.resolution=.5
    message.info.origin.orientation.w=1.;message.data=[-1,0]
    checks={}

    def check(name,condition):
        checks[name]=bool(condition)
        if not condition:raise AssertionError(name)

    check('Gateway_default_off',inspect.signature(Gateway).parameters['capture_central_map'].default is False)
    off.capture(89,message)
    check('TopicWire_default_off',off.central_map_capture is None and not gateway.central_map_captures)
    check('same_topics_and_QoS',off_node.subscriptions==on_node.subscriptions
        and off_node.publishers==on_node.publishers)
    with (patch.object(topic_wire,'serialize_message',wraps=topic_wire.serialize_message) as serialize,
          patch.object(topic_wire.hashlib,'sha256',wraps=topic_wire.hashlib.sha256) as sha):
        on.capture(89,message)
        check('one_serialization_and_existing_hash_only',serialize.call_count==sha.call_count==1)
    body,row,gz=gateway.central_map_captures[0]
    check('same_body_and_row_references',body is sent[-1][3] and row is on.captured[0])
    check('original_CDR_and_metadata',deserialize_message(body,OccupancyGrid)==message
        and row['flow']==89 and row['bytes']==len(body) and len(row['cdr_sha256'])==64
        and row['source_stamp_ns']==2_000_000_000 and row['source_stamp_available']
        and row['capture_node_sim_ns']==9_000_000_000
        and row['endpoint_capture_monotonic_ns']>0 and gz==8_900_000_000)
    on.capture(30,message);r.capture(21,message);r.capture(89,message)
    check('only_C_flow89_retained',len(gateway.central_map_captures)==1)
    check('no_extra_publish_or_send',len(sent)==5 and not any(
        node.published for node in (off_node,on_node,r_node)))
    check('RAM_only_before_persist',not list(args.directory.iterdir()))
    # A failing spy proves the persistence path does not serialize/hash again.
    with (patch.object(topic_wire,'serialize_message',side_effect=AssertionError('second serialization')),
          patch.object(topic_wire.hashlib,'sha256',side_effect=AssertionError('second hash'))):
        gateway.persist_central_maps()
    directory=args.directory/'central-map-capture'
    index=json.loads((directory/'index.json').read_text())
    sample=index['samples'][0]
    check('persist_exact_CDR_and_reused_metadata',index['scope']=='C_Gateway_capture'
        and len(index['samples'])==1 and (directory/sample['cdr_file']).read_bytes()==body
        and sample==dict(row,cdr_file='000000.cdr',last_observed_R_clock_ns=gz))
    result=dict(status='PASS',checks=checks,scope='Real ROS type/CDR only; 0 rclpy.init, Node, '
        'DDS, GZ, navigation, policy or network runs; send/publication are counted doubles.')
    (args.directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
