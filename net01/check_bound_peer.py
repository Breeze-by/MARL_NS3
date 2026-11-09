"""No-Node actual ROS message/CDR check of publication-batch observation only."""
from array import array
import argparse
import json
from pathlib import Path
import struct
from rclpy.serialization import serialize_message,deserialize_message
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import String
from bound_peer import BatchBinding,ObservedPublisher,decode_bound


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    result=dict(status="FAIL",scope="No ROS init/Node; observe actual typed publish arguments and original serialized mask values; not live SLAM/ROS safety",checks={},ROS_Node=0,Gazebo=0,NN=0)
    order=[];original={};packets={};before={};observed_cdr={}
    def check(name,value):
        if not value:raise AssertionError(name)
        result["checks"][name]=True
    class Publisher:
        def __init__(self,name):self.name=name
        def publish(self,message):
            order.append(self.name)
            original[self.name]=bytes(serialize_message(message))
    def output(robot,packet):
        order.append("bound_"+robot);packets[robot]=packet
    binding=BatchBinding(output,17)
    state=dict(ready=True,generated_sim=100.,sequence=9,
        odom_stamps={r:99.9 for r in ("tb1","tb2","tb3")},
        correction_stamps={r:100.1 for r in ("tb1","tb2","tb3")})
    try:
        for robot in ("tb1","tb2","tb3"):
            msg=OccupancyGrid();msg.header.frame_id="odom";msg.header.stamp.sec=100
            msg.header.stamp.nanosec=1_000_000;msg.info.resolution=.05
            msg.info.width=msg.info.height=400;msg.info.origin.orientation.w=1.
            msg.data=array("b",[-1])*160000;msg.data[int(robot[-1])]=100
            before[robot]=deserialize_message(serialize_message(msg),OccupancyGrid)
            wrapper=ObservedPublisher(Publisher(robot),lambda m,r=robot:binding.mask(r,m))
            wrapper.publish(msg)
            observed_cdr[robot]=binding.pending[robot][0]
        health=String(data=json.dumps(state));ObservedPublisher(Publisher("health"),binding.health).publish(health)
        check("original_three_mask_then_health_real_publish_order_unchanged",order[:4]==["tb1","tb2","tb3","health"])
        check("binding_only_after_actual_health_publish",order[4:]==["bound_tb1","bound_tb2","bound_tb3"])
        overhead={}
        for robot,packet in packets.items():
            metadata,message=decode_bound(packet,robot,17)
            check(robot+"_all_original_mask_fields_unchanged",message==before[robot])
            n,=struct.unpack("!I",packet[:4]);body=packet[4+n:]
            check(robot+"_original_publish_all_fields_equal",message==deserialize_message(original[robot],OccupancyGrid))
            check(robot+"_captured_CDR_exact_in_envelope",body==observed_cdr[robot])
            check(robot+"_actual_same_health_state_bound",metadata["bound_state"]==state)
            overhead[robot]=dict(original_CDR_bytes=len(body),transport_binding_bytes=len(packet)-len(body),bound_bytes=len(packet))
        # A later 'latest' value cannot replace a previously captured batch.
        health.data=json.dumps(dict(state,sequence=10,odom_stamps={r:999. for r in state["odom_stamps"]}))
        check("later_health_object_does_not_rebind_old_mask",all(decode_bound(p,r,17)[0]["bound_state"]["sequence"]==9 for r,p in packets.items()))
        rejected=[]
        for name,packet,robot,session in [
            ("wrong_epoch",packets["tb1"],"tb1",18),
            ("wrong_robot",packets["tb1"],"tb2",17),
            ("changed_mask_bytes",packets["tb1"][:-1]+bytes([packets["tb1"][-1]^1]),"tb1",17)]:
            try:decode_bound(packet,robot,session)
            except ValueError:rejected.append(name)
        check("mismatched_epoch_robot_content_rejected",len(rejected)==3)
        try:binding.health(health)
        except RuntimeError:check("health_without_three_actual_masks_never_uses_latest_cache",True)
        else:raise AssertionError("Incomplete batch incorrectly bound")
        result.update(status="PASS",overhead=overhead,order=order,
            guard_and_network_scope="No guard/Action/physical stop tested; only publication provenance and exact bytes")
    except BaseException as error:
        result["error"]=repr(error);raise
    finally:
        (args.output/"result.json").write_text(json.dumps(result,indent=2)+"\n")


if __name__=="__main__":main()
