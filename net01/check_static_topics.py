"""Two-domain real DDS/CDR normal-load fixture over the actual ns3 IPC hub.

No Nav2, Action/velocity command, policy or Gazebo. Controlled timestamps are
explicit synthetic load metadata; this does not certify the real /clock gate.
"""
import argparse
from array import array
from collections import Counter, defaultdict
import json
from pathlib import Path
import time

import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.serialization import serialize_message, deserialize_message
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import OccupancyGrid, Odometry
from tf2_msgs.msg import TFMessage
from std_msgs.msg import String
from nav2_msgs.msg import CostmapFilterInfo

from hub_client import HubClient
from topic_wire import TopicWire, flows, qos
from link_session import LinkSession


def stamp(header, ns, frame):
    header.frame_id = frame
    header.stamp.sec, header.stamp.nanosec = divmod(ns, 1_000_000_000)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = dict(status="FAIL", scope="Real ROS2 FastRTPS R92/C91 topic serialization/publication over native ns3 WiFi; synthetic timestamps and controlled ticks, no GZ/Action/network safety acceptance",
        domains={"R":92,"C":91}, Gazebo=0, NN=0, velocity_command_publishers=0)
    context, nodes, executors, wires = {}, {}, {}, {}
    expected, observed = Counter(), Counter()
    expected_fields, observed_fields = defaultdict(list), defaultdict(list)
    observed_meta = []
    hub = HubClient(args.socket)
    link = LinkSession(hub, session_id=3)
    specs = flows()
    start = time.monotonic()
    deadline = start+75

    def pump():
        if time.monotonic() > deadline:
            raise TimeoutError("75wall static fixture bound")
        hub.poll()
        for executor in executors.values():
            executor.spin_once(timeout_sec=0)

    def until(predicate, limit=8):
        end = min(deadline,time.monotonic()+limit)
        while not predicate() and time.monotonic()<end:
            pump()
        if not predicate():
            raise TimeoutError("Static DDS/native condition deadline")

    def tick(ns):
        hub.clock(ns)
        until(lambda:hub.horizon_ns==ns)

    def consumer(flow, message):
        body = bytes(serialize_message(message))
        observed[flow] += 1
        observed_fields[flow].append(message)
        observed_meta.append(dict(flow=flow, cdr_bytes=len(body), receive_monotonic_ns=time.monotonic_ns(),
            controlled_horizon_ns=hub.horizon_ns))

    try:
        until(lambda:hub.ready)
        for side, domain in (("R",92),("C",91)):
            context[side] = Context()
            rclpy.init(context=context[side],domain_id=domain)
            nodes[side] = Node("net01_static_"+side.lower(),context=context[side])
            executors[side] = SingleThreadedExecutor(context=context[side])
            executors[side].add_node(nodes[side])
        source_publishers, consumers = {}, []
        for flow, spec in specs.items():
            source_side, target_side = (("R","C") if spec["direction"]=="up" else ("C","R"))
            topic = spec["topic"]
            key = (source_side,topic)
            if key not in source_publishers:
                source_publishers[key] = nodes[source_side].create_publisher(spec["cls"],topic,qos(spec))
            consumers.append(nodes[target_side].create_subscription(spec["cls"],spec.get("received_topic",topic),
                lambda msg, f=flow:consumer(f,msg),qos(spec)))

        def delivered(meta, cdr, rpc_id):
            if link.receive(meta,cdr,rpc_id):
                return
            side = "C" if meta["receiver"]==0 else "R"
            wires[side].receive(meta,cdr,rpc_id)
        hub.receive = delivered
        samples = []

        def publish(flow, message, expect_delivery=True):
            spec = specs[flow]
            side = "R" if spec["direction"]=="up" else "C"
            body = bytes(serialize_message(message))
            peers = [flow]
            if spec["topic"]=="/peer_keepout_state":
                peers = [r*20+11 for r in (1,2,3)]
            if expect_delivery:
                for target in peers:
                    expected[target] += 1
                    # ROS CDR float32 fields are normalized at serialization.
                    # CDR alignment padding is not a message field and need not
                    # survive the separate DDS deserialize/serialize stages.
                    expected_fields[target].append(deserialize_message(body,spec["cls"]))
            source_publishers[(side,spec["topic"])].publish(message)
            return len(body)

        def grid(flow, ns, size):
            message = OccupancyGrid()
            stamp(message.header,ns,"odom" if flow%20==10 else "map")
            message.info.resolution=.05
            message.info.width,message.info.height = ((400,400) if size==160000 else (250,220) if size==55000 else (60,60))
            message.info.origin.position.x=-10.0 if size==160000 else -6.0
            message.info.origin.position.y=-10.0 if size==160000 else -5.0
            message.info.origin.orientation.w=1.
            message.data=array("b", ((-1,0,100)[(i+flow)%3] for i in range(size)))
            return message

        # Sources retain real DDS TL samples before business subscriptions.
        for robot in (1,2,3):
            base=robot*20
            publish(base+1,grid(base+1,0,55000))
            transform=TransformStamped();stamp(transform.header,0,"merge_map")
            transform.child_frame_id="map";transform.transform.rotation.w=1.
            publish(base+4,TFMessage(transforms=[transform]))
            info=CostmapFilterInfo();info.type=0;info.base=0.;info.multiplier=1.
            info.filter_mask_topic=f"/tb{robot}/peer_keepout_mask"
            publish(base+12,info)
        # Execute actual association/beacon events. Elapsed time alone is NOT
        # link readiness: every STA must really receive HELLO and return ACK.
        for ns in range(100_000_000,600_000_001,100_000_000):tick(ns)
        link.begin()
        for ns in range(700_000_000,2_100_000_001,100_000_000):
            tick(ns)
            if link.ready:break
        if not link.ready:raise TimeoutError("Finite real HELLO/ACK failed")
        for side in ("R","C"):wires[side]=TopicWire(nodes[side],side,hub.send)
        until(lambda:all(pub.get_subscription_count()>0 for pub in source_publishers.values()))
        until(lambda:all(pub.get_subscription_count()>0 for wire in wires.values() for pub in wire.publishers.values()))
        until(lambda:sum(len(w.captured) for w in wires.values())==9)
        load_start=hub.horizon_ns+100_000_000
        tick(load_start)
        until(lambda:sum(observed.values())==9)

        # The fixture has the frozen publisher/consumer types and QoS. Per10Hz
        # quantum odom3/TF10 are a conservative same-tick burst of the original
        # 30/100Hz average load, with original headers at <=the captured tick.
        # A 2sim-second window is fixed, not a throughput parameter sweep.
        for index in range(20):
            current=load_start+index*100_000_000
            capture_before=sum(len(w.captured) for w in wires.values())
            expected_before=sum(expected.values())
            counts = Counter()
            for robot in (1,2,3):
                base=robot*20
                for j in range(3):
                    msg=Odometry();stamp(msg.header,current-(2-j)*33_333_333,"odom")
                    msg.child_frame_id="base_footprint";msg.pose.pose.orientation.w=1.
                    publish(base+2,msg);counts["odom"]+=1
                for j in range(10):
                    transform=TransformStamped();stamp(transform.header,current-(9-j)*10_000_000,"odom")
                    transform.child_frame_id="base_footprint";transform.transform.rotation.w=1.
                    publish(base+3,TFMessage(transforms=[transform]));counts["tf"]+=1
                mask_bytes=publish(base+10,grid(base+10,current,160000));counts["masks"]+=1
                if index%5==0:
                    publish(base+5,grid(base+5,current,3600));counts["local_costmap"]+=1
            state=String(data=json.dumps(dict(sequence=index+1,generated_sim=current/1e9,ready=True,
                odom_stamps={f"tb{r}":current/1e9 for r in (1,2,3)},
                correction_stamps={f"tb{r}":current/1e9+.2 for r in (1,2,3)},
                scope="STATIC ROS BUSINESS FIXTURE, NOT REAL SLAM STATE")))
            publish(31,state);counts["health_source"]+=1
            added=sum(expected.values())-expected_before
            until(lambda:sum(len(w.captured) for w in wires.values())==capture_before+added)
            # Enqueued sends precede this clock command on the sole owned pipe.
            tick(current+100_000_000)
            samples.append(dict(source_quantum_ns=current, counts=dict(counts), serialized_mask_bytes_each=mask_bytes,
                expected_messages=sum(expected.values()), native_deliveries=len(hub.deliveries),
                DDS_consumer_messages=sum(observed.values()), wall_since_start=time.monotonic()-start))
        # Bound the trailing partial-tick/ROS delivery; no retransmit or refresh.
        for ns in range(load_start+2_100_000_000,load_start+2_600_000_001,100_000_000):
            tick(ns)
        until(lambda:sum(observed.values())==sum(expected.values()),limit=5)
        if observed!=expected or any(observed_fields[f]!=v for f,v in expected_fields.items()):
            raise AssertionError("Whole CDR/destination/sequence differs after actual network and DDS delivery")
        positive_count=sum(observed.values())
        # Actual PHY blackout while source DDS nodes continue creating new CDR.
        # The hub accepts this control only under its explicit no-motion-test flag.
        hub.radio_fault(False)
        before=sum(len(w.captured) for w in wires.values())
        blackout_start=hub.horizon_ns
        publish(21,grid(21,blackout_start,55000),False)
        publish(30,grid(30,blackout_start,160000),False)
        until(lambda:sum(len(w.captured) for w in wires.values())==before+2)
        for ns in range(blackout_start+100_000_000,blackout_start+900_000_001,100_000_000):
            tick(ns)
        if sum(observed.values())!=positive_count:
            raise AssertionError("New ROS business bypassed disabled WiFi PHY")
        hub.radio_fault(True)
        before=sum(len(w.captured) for w in wires.values())
        recovery_start=hub.horizon_ns
        publish(21,grid(21,recovery_start,55000))
        publish(30,grid(30,recovery_start,160000))
        until(lambda:sum(len(w.captured) for w in wires.values())==before+2)
        for ns in range(recovery_start+100_000_000,recovery_start+600_000_001,100_000_000):
            tick(ns)
        until(lambda:sum(observed.values())==sum(expected.values()),limit=5)
        if observed!=expected or any(observed_fields[f]!=v for f,v in expected_fields.items()):
            raise AssertionError("Recovery used old blocked CDR or mismatched a new source")
        captured_cdr=Counter((x["flow"],x["cdr_sha256"]) for wire in wires.values() for x in wire.captured)
        received_cdr=Counter((x["flow"],x["cdr_sha256"]) for wire in wires.values() for x in wire.delivered)
        # The two explicit blackout messages are absent; all positive wire
        # CDR bytes must be identical, including their original padding.
        unmatched=captured_cdr-received_cdr
        if sum(unmatched.values())!=2 or received_cdr-captured_cdr:
            raise AssertionError("Actual CDR wire content identity changed")
        result.update(status="PASS", wall_s=time.monotonic()-start,
            source_window_sim_s=2., quantum_sim_s=.1,
            checks=dict(captured_to_received_full_CDR_bytes_exact=True, each_real_DDS_consumer_fields_exact=True, R_C_domain_separate=True,
                three_160KB_masks_10Hz=True, health_10Hz_each_STA=True, odom30Hz_TF100Hz_average_within_tick_bursts=True,
                original_map_and_filter_QoS=True, source_header_preserved=True),
            actual_link_qualification=dict(all_three_double_direction_ACKs=link.ready,events=link.events),
            no_bypass_negative=dict(actual_PHY_off_new_DDS_map_and_mask_no_consumer=True,
                resumed_only_new_header_exact=True, direct_C_R_DDS_did_not_fill_missing_messages=True),
            average_lower_bound_mask_CDR_bytes_per_sim_s=20*3*samples[0]["serialized_mask_bytes_each"]/2,
            capture_counts={side:len(w.captured) for side,w in wires.items()},
            delivered_counts={side:len(w.delivered) for side,w in wires.items()},
            total_DDS_messages=sum(observed.values()), total_CDR_bytes=sum(x["cdr_bytes"] for wire in wires.values() for x in wire.delivered),
            samples=samples,
            limitations=["Controlled static timestamps and batched per-.1sim generation, not Gazebo source timing", "Endpoint DDS reliable/transient-local does not make UDP reassembly end-to-end reliable", "No Action, physical navigation, real /clock, network disconnect safety or policy inference tested"])
    except BaseException as error:
        result["error"]=f"{type(error).__name__}: {error}"
        raise
    finally:
        (args.output/"result.json").write_text(json.dumps(result,indent=2)+"\n")
        (args.output/"link-qualification.json").write_text(json.dumps(link.events,indent=2)+"\n")
        (args.output/"endpoint-captures.json").write_text(json.dumps({s:w.captured for s,w in wires.items()},indent=2)+"\n")
        (args.output/"endpoint-deliveries.json").write_text(json.dumps({s:w.delivered for s,w in wires.items()},indent=2)+"\n")
        (args.output/"real-DDS-consumers.json").write_text(json.dumps(observed_meta,indent=2)+"\n")
        hub.end()
        end=time.monotonic()+2
        while hub.outgoing and time.monotonic()<end:
            hub.poll()
        hub.close()
        for executor in executors.values():executor.shutdown(timeout_sec=0.)
        for node in nodes.values():node.destroy_node()
        for item in context.values():item.shutdown()


if __name__=="__main__":
    main()
