"""Comparison-only direct ROS reference with common admin/evaluation boundaries.

The original direct safety registry and no-business-wire guard remain active.
The journal is local R DDS; no payload enters the native network in this arm.
"""
import time
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import String
from a0_gateway import DirectReferenceGateway
from execution_profile import COMPARISON_PROFILE_IDS
from gateway import Gateway
from topic_wire import flows,qos


class ComparisonDirectReferenceGateway(DirectReferenceGateway):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.execution_profile['id'] not in COMPARISON_PROFILE_IDS:
            raise ValueError('Comparison direct adapter requires its explicit new profile')
        self.central_capture_side='R';self.central_capture_domain=92
        # Base C timer/position retained: only the local publisher's domain
        # changes for direct HQ's original journal, without business wires.
        self.journal_pub=self.r.create_publisher(String,'/net01/controller_records',100)
        if self.central_map_captures is not None:
            self.direct_central_map_sub=self.r.create_subscription(OccupancyGrid,'/merge_map',
                self.capture_direct_central_map,qos(flows(runtime=True)[89]),raw=True)

    def _export_controller_records(self):
        return Gateway._export_controller_records_to(self,self.journal_pub,require_business_wires=False)

    def capture_direct_central_map(self,body):
        row=dict(flow=89,topic='/merge_map',bytes=len(body),
            endpoint_capture_monotonic_ns=time.monotonic_ns(),
            capture_node_sim_ns=self.r.get_clock().now().nanoseconds,
            source_stamp_ns=None,source_stamp_available=False,
            source_stamp_status='Unparsed live raw capture; original header remains in saved CDR',
            actual_business_transport='A0_direct_R92_DDS_no_native_business')
        self.retain_central_map(body,row)
