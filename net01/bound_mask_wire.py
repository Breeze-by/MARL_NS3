"""Transport original bound masks and publish only validated actual arrivals."""
import json
from rclpy.qos import QoSProfile,DurabilityPolicy
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import UInt8MultiArray
from bound_peer import decode_bound


class BoundMaskWire:
    def __init__(self,node,side,send,session_id,accept_bound):
        self.side,self.send,self.session_id=side,send,session_id
        self.accept_bound=accept_bound
        self.publishers={};self.subscriptions=[];self.received=[]
        qos=QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        for robot in (1,2,3):
            if side=="C":
                self.subscriptions.append(node.create_subscription(UInt8MultiArray,
                    f"/net01/tb{robot}/peer_mask_bound",lambda msg,r=robot:self.capture(r,msg),qos))
            else:
                self.publishers[robot]=node.create_publisher(OccupancyGrid,f"/tb{robot}/peer_keepout_mask",qos)

    def capture(self,robot,message):
        # Metadata/body are both the actual C publisher's bytes, not a source lookup.
        packet=bytes(message.data)
        meta,_=decode_bound(packet,f"tb{robot}",self.session_id)
        h=meta["original_header"]
        self.send(0,robot,robot*20+10,packet,0,h["stamp_sec"]*1_000_000_000+h["stamp_nanosec"])

    def receive(self,meta,packet,rpc_id):
        robot=meta["receiver"]
        if self.side!="R" or meta["sender"]!=0 or robot not in self.publishers or meta["flow"]!=robot*20+10 or rpc_id:
            raise ValueError("Wrong mask destination/flow")
        binding,message=decode_bound(packet,f"tb{robot}",self.session_id)
        accepted=self.accept_bound(robot,binding,meta)
        self.received.append(dict(native=meta,binding=binding,accepted=accepted))
        if accepted:self.publishers[robot].publish(message)
