"""Fresh 89/95 negative: actual DDS, Gateway methods and ns-3; never navigation."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[3]
CASE=REPO/'net01d/followup02/runs/fresh-8995-01'
RAM=Path('/dev/shm/net01d-f02-fresh8995-01')
SESSION=2026111102
NONCE='net01d-fresh8995-01'
CUT_BEGIN=3_000_000_000
CUT_END=3_600_000_000
END=8_000_000_000


def save(path,value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')


def worker(socket_path,output):
    from array import array
    from unittest.mock import patch
    import rclpy
    from rclpy.context import Context
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.signals import SignalHandlerOptions
    from rclpy.serialization import serialize_message,deserialize_message
    from nav_msgs.msg import OccupancyGrid
    from std_msgs.msg import String
    from gateway import Gateway
    from hub_client import HubClient
    from link_session import LinkSession
    import topic_wire

    output.mkdir()
    result=dict(status='FAIL',scope='Fresh actual 89/95 data paths, not complete Gateway lifecycle',
        source_clock='Explicit synthetic fixture / native KNOWN ticks; no Gazebo /clock or synchrony claim',
        domains=dict(C=91,R=92),ROS_Action=0,Nav2=0,velocity_publishers=0,Gazebo=0,NN=0)
    start=time.monotonic();deadline=start+25
    contexts=[];nodes=[];executors=[];expected={};received=[];wire_arrivals=[];source_rows=[]
    hub=None;adapter=None;first_error=None
    specs={flow:spec for flow,spec in topic_wire.flows(runtime=True).items() if flow in (89,95)}

    def interrupted(number,_frame):raise InterruptedError(f'Fresh fixture signal {number}')
    signal.signal(signal.SIGTERM,interrupted)

    def identity(flow,message):
        if flow==89:
            if message.info.map_load_time.sec!=SESSION:raise ValueError('Foreign map session')
            return message.info.map_load_time.nanosec
        value=json.loads(message.data)
        if value['nonce']!=NONCE or value['session']!=SESSION:raise ValueError('Foreign journal nonce')
        return value['sequence']

    def pump():
        if time.monotonic()>=deadline:raise TimeoutError('25wall fresh worker bound')
        hub.poll()
        for executor in executors:executor.spin_once(timeout_sec=0.)
        time.sleep(.0005)

    def until(predicate):
        while not predicate():pump()

    def tick(ns):
        # Admin clock is explicit fixture input, never a robot observation.
        adapter.gz=ns
        hub.observed_clock(ns);hub.clock(ns)
        until(lambda:hub.horizon_ns==ns)

    def to(ns):
        for value in range(hub.horizon_ns+10_000_000,ns+1,10_000_000):tick(value)

    def consume(flow,message):
        seq=identity(flow,message)
        if message!=expected[(flow,seq)]:raise ValueError('Typed destination fields changed')
        row=dict(flow=flow,sequence=seq,nonce=NONCE,monotonic_ns=time.monotonic_ns(),
            horizon_ns=hub.horizon_ns)
        received.append(row)
        if seq in (2,3,4) and CUT_BEGIN<=hub.horizon_ns<CUT_END:
            raise AssertionError('Fresh cut-period nonce reached DDS consumer while WiFi disabled')

    try:
        for side,domain in (('C',91),('R',92)):
            context=Context();rclpy.init(context=context,domain_id=domain,
                signal_handler_options=SignalHandlerOptions.NO)
            node=Node('net01_fresh8995_'+side.lower(),context=context)
            executor=SingleThreadedExecutor(context=context);executor.add_node(node)
            contexts.append(context);nodes.append(node);executors.append(executor)
        hub=HubClient(socket_path)
        # Use actual production send/receive methods without constructing
        # unrelated Action/LocalStop/cmd_vel entities or their exit actions.
        adapter=Gateway.__new__(Gateway)
        adapter.mode='B';adapter.failure=None;adapter.anchor=dict(offset_ns=0)
        adapter.gz=0;adapter.records=[];adapter.hub=hub;adapter.wires=None
        adapter.link=LinkSession(adapter,SESSION)
        def delivered(meta,cdr,rpc):
            if meta['flow'] in specs:
                message=deserialize_message(cdr,specs[meta['flow']]['cls'])
                wire_arrivals.append(dict(meta,sequence=identity(meta['flow'],message),
                    nonce=NONCE,endpoint_monotonic_ns=time.monotonic_ns()))
            adapter.receive(meta,cdr,rpc)
        hub.receive=delivered
        until(lambda:hub.ready)
        adapter.link.begin();to(2_500_000_000)
        if not adapter.link.ready:raise AssertionError('Three actual HELLO/ACK exchanges absent')
        # Selection affects only this fixture's constructor calls. The actual
        # production TopicWire capture/receive/flow QoS implementations remain.
        with patch.object(topic_wire,'flows',return_value=specs):
            adapter.wires={side:topic_wire.TopicWire(node,side,adapter.send,runtime=True)
                for side,node in zip(('C','R'),nodes)}
        publishers={flow:nodes[0].create_publisher(spec['cls'],spec['topic'],topic_wire.qos(spec))
            for flow,spec in specs.items()}
        subscriptions=[nodes[1].create_subscription(spec['cls'],spec['topic'],
            lambda message,flow=flow:consume(flow,message),topic_wire.qos(spec))
            for flow,spec in specs.items()]
        until(lambda:all(pub.get_subscription_count()>0 for pub in publishers.values()) and
            all(pub.get_subscription_count()>0 for pub in adapter.wires['R'].publishers.values()))

        def publish(seq):
            before=len(adapter.wires['C'].captured)
            grid=OccupancyGrid();grid.header.frame_id='merge_map'
            grid.header.stamp.sec,grid.header.stamp.nanosec=divmod(hub.horizon_ns,1_000_000_000)
            grid.info.resolution=.05;grid.info.width=250;grid.info.height=220
            grid.info.origin.orientation.w=1.
            grid.info.map_load_time.sec=SESSION;grid.info.map_load_time.nanosec=seq
            pattern=[ord(char)%101 for char in NONCE]+[seq]
            grid.data=array('b',(pattern[i%len(pattern)] for i in range(55_000)))
            journal=String(data=json.dumps(dict(nonce=NONCE,session=SESSION,sequence=seq,
                origin='controlled real C91 publisher; no HQ/Policy',source_horizon_ns=hub.horizon_ns)))
            for flow,message in ((89,grid),(95,journal)):
                expected[(flow,seq)]=deserialize_message(serialize_message(message),specs[flow]['cls'])
                publishers[flow].publish(message)
                source_rows.append(dict(flow=flow,sequence=seq,nonce=NONCE,
                    horizon_ns=hub.horizon_ns,publish_return_monotonic_ns=time.monotonic_ns()))
            until(lambda:len(adapter.wires['C'].captured)==before+2)

        publish(1);to(CUT_BEGIN)
        until(lambda:all(any(r['flow']==flow and r['sequence']==1 for r in received) for flow in (89,95)))
        if {(r['flow'],r['sequence']) for r in received}!={(89,1),(95,1)}:
            raise AssertionError('Fresh positive pair not delivered before cut')
        hub.radio_fault(False);tick(CUT_BEGIN+10_000_000)
        for seq,at in ((2,3_010_000_000),(3,3_110_000_000),(4,3_210_000_000)):
            to(at);publish(seq)
        to(CUT_END)
        cut_observed=[r for r in received if r['sequence'] in (2,3,4)]
        cut_wire=[r for r in wire_arrivals if r['sequence'] in (2,3,4) and r['ns3_rx_ns']<CUT_END]
        if cut_observed or cut_wire:raise AssertionError('Fresh 89/95 bypass during actual radio blackout')
        hub.radio_fault(True);tick(CUT_END+10_000_000);publish(5);to(END)
        until(lambda:all(any(r['flow']==flow and r['sequence']==5 for r in received) for flow in (89,95)))
        keys=[(r['flow'],r['sequence']) for r in received]
        if len(keys)!=len(set(keys)):raise AssertionError('Duplicate typed business identity')
        result.update(status='PASS_FRESH_89_95_ONLY',source=source_rows,consumers=received,
            actual_wire_arrivals=wire_arrivals,
            late_cut_identities_after_restore=[r for r in wire_arrivals if r['sequence'] in (2,3,4)],
            checks=dict(positive_fresh_pair=True,C_cut_publish_and_capture_6=True,
                no_cut_nonce_at_R_before_restore=True,recovery_fresh_pair=True,
                real_three_direction_HELLO_ACK=adapter.link.ready),
            limitations=['Synthetic fixture clocks, no wall latency/safety certificate',
                'Only production 89/95 send/receive/data/QoS paths, not full Gateway constructor/dispatcher/exit',
                'Cut samples delivered after restoration are late, not proven lost'])
    except BaseException as error:
        first_error=repr(error);result.update(status='FAIL',first_error=first_error)
    finally:
        result.update(source=source_rows,consumers=received,actual_wire_arrivals=wire_arrivals,
            late_cut_identities_after_restore=[r for r in wire_arrivals
                if r['sequence'] in (2,3,4) and r['ns3_rx_ns']>=CUT_END])
        if adapter is not None:
            result.update(link=adapter.link.events,Gateway_records=adapter.records,
                captures=None if adapter.wires is None else adapter.wires['C'].captured,
                destination_publications=None if adapter.wires is None else adapter.wires['R'].delivered)
        if hub is not None:
            try:
                hub.end();end=min(deadline+1,time.monotonic()+1)
                while hub.outgoing and time.monotonic()<end:hub.poll();time.sleep(.0005)
                result['END_frame_flushed']=not hub.outgoing
                if hub.outgoing:
                    result.setdefault('first_error','Fixture END frame not flushed before bound')
                    result['status']='FAIL'
            except (OSError,EOFError) as error:
                result.setdefault('first_error',repr(error));result['status']='FAIL'
            finally:hub.close()
        for executor in executors:executor.shutdown(timeout_sec=0.)
        for node in nodes:node.destroy_node()
        for context in contexts:context.shutdown()
        result['wall_s']=time.monotonic()-start
        save(output/'result.json',result)
    return 0 if result['status']=='PASS_FRESH_89_95_ONLY' else 1


def host(native):
    if not native.is_absolute() or not native.is_file():raise FileNotFoundError(native)
    CASE.mkdir(parents=True,exist_ok=False)
    if RAM.exists():raise FileExistsError(RAM)
    started=time.monotonic();deadline=started+30;processes=[];logs=[]
    result=dict(status='FAIL',scope='native TCP fresh89/95 no-motion transport negative; no ROS Action/Gazebo',
        source_clock='synthetic KNOWN/STEP',native=str(native),resources=[],forced=[])
    def interrupted(number,_frame):raise InterruptedError(f'Fresh host signal {number}')
    signal.signal(signal.SIGTERM,interrupted)
    try:
        hubcmd=[sys.executable,'-B',str(REPO/'net01/tools/packet_hub.py'),
            '--socket',str(CASE/'wire.sock'),'--native',str(native),'--output',str(CASE/'hub'),
            '--native-transport','tcp-v1','--profile','B','--clock-source','gazebo',
            '--allow-radio-fault','--control-trace','--wall','28','--native-evidence-ram',str(RAM)]
        workercmd=['bash',str(REPO/'net01/ros-python.sh'),
            '/mnt/net01d/followup02/transport/check_fresh_89_95.py','--worker',
            '--socket','/mnt/'+str((CASE/'wire.sock').relative_to(REPO)),
            '--output','/mnt/'+str((CASE/'ros').relative_to(REPO))]
        save(CASE/'argv.json',dict(hub=hubcmd,worker=workercmd))
        for role,command in (('hub',hubcmd),('worker',workercmd)):
            if role=='worker':
                while not (CASE/'wire.sock').exists():
                    if time.monotonic()>deadline or processes[0][1].poll() is not None:
                        raise RuntimeError('Hub failed before fresh ROS worker')
                    time.sleep(.005)
            log=(CASE/(role+'.log')).open('x');logs.append(log)
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            processes.append((role,process))
        processes[1][1].wait(timeout=max(.01,deadline-time.monotonic()))
        processes[0][1].wait(timeout=max(.01,deadline-time.monotonic()))
        raw= json.loads((CASE/'ros/result.json').read_text())
        hubresult=json.loads((CASE/'hub/result.json').read_text())
        config=json.loads((CASE/'hub/native/transport-config.json').read_text())
        native_summary=json.loads((CASE/'hub/native/native-summary.json').read_text())
        counts=native_summary['counts']
        if (any(process.returncode!=0 for _,process in processes) or raw['status']!='PASS_FRESH_89_95_ONLY'
                or hubresult['status']!='PASS' or not hubresult['native_evidence_storage']['complete']
                or hubresult.get('error') or counts.get('tcp_connected')!=3 or counts.get('tcp_accepted')!=3
                or counts.get('channel_blackout')!=1 or counts.get('channel_restored')!=1):
            raise AssertionError('Fresh business/native/process evidence incomplete')
        result.update(status='PASS_FRESH_89_95_ONLY',native_config=config,native_counts=counts,
            late_cut_identities=raw['late_cut_identities_after_restore'],raw_Hub_result=hubresult)
    except BaseException as error:result.update(status='FAIL',first_error=repr(error))
    finally:
        for role,process in reversed(processes):
            try:os.killpg(process.pid,0)
            except ProcessLookupError:pass
            else:
                os.killpg(process.pid,signal.SIGKILL);result['forced'].append(dict(role=role,signal='SIGKILL'))
                process.wait(timeout=1.)
            result['resources'].append(dict(role=role,pid=process.pid,exit=process.poll()))
        for log in logs:log.close()
        if result['forced']:result['status']='FAIL'
        result['wall_s']=time.monotonic()-started;save(CASE/'result.json',result)
    return 0 if result['status']=='PASS_FRESH_89_95_ONLY' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--native',type=Path)
    parser.add_argument('--worker',action='store_true');parser.add_argument('--socket',type=Path)
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    raise SystemExit(worker(args.socket,args.output) if args.worker else host(args.native))
