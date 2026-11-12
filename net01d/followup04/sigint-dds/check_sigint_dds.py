"""One fixed real-DDS workload and one default-Python SIGINT, diagnostic only."""
import argparse
from array import array
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

import rclpy
from rclpy.context import Context
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from rclpy.serialization import serialize_message
from rclpy.signals import SignalHandlerOptions
from nav_msgs.msg import OccupancyGrid

DOMAIN=97
TOPIC='/net01d/sigint_diagnostic/grid'
WIDTH=HEIGHT=400
PERIOD=.05
SUPPLY_WALL=12.


def save(path,data):
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('x') as stream:json.dump(data,stream,indent=2);stream.write('\n')
    temporary.rename(path)


def exception_record(error):
    """Observe existing traceback only; do not call or wrap any take method."""
    row=dict(monotonic_ns=time.monotonic_ns(),utc=datetime.now(timezone.utc).isoformat(),
        type=type(error).__name__,module=type(error).__module__,message=str(error),
        cause=None if error.__cause__ is None else dict(type=type(error.__cause__).__name__,repr=repr(error.__cause__)),
        context=None if error.__context__ is None else dict(type=type(error.__context__).__name__,repr=repr(error.__context__)),
        suppress_context=error.__suppress_context__,traceback=''.join(traceback.format_exception(type(error),error,error.__traceback__)),frames=[])
    tb=error.__traceback__
    while tb is not None:
        frame=tb.tb_frame
        item=dict(file=frame.f_code.co_filename,function=frame.f_code.co_name,line=tb.tb_lineno)
        if frame.f_code.co_name=='_take_subscription':
            sub=frame.f_locals.get('sub')
            item['subscription_present']=sub is not None
            if sub is not None:
                # These public properties are read before finally destroys the
                # Node; an observation failure must not replace the original.
                try:item.update(topic_name=sub.topic_name,msg_type_module=sub.msg_type.__module__,msg_type_name=sub.msg_type.__name__,raw=sub.raw)
                except Exception as metadata_error:item['metadata_read_error']=repr(metadata_error)
        row['frames'].append(item);tb=tb.tb_next
    return row


def receiver(directory):
    context=rclpy.get_default_context()
    rclpy.init(context=context,domain_id=DOMAIN,signal_handler_options=SignalHandlerOptions.NO)
    node=Node('net01d_one_sigint_receiver',context=context)
    count=0
    def received(message):
        nonlocal count
        count+=1
    sub=node.create_subscription(OccupancyGrid,TOPIC,received,
        QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL),raw=False)
    save(directory/'receiver-ready.json',dict(pid=os.getpid(),ppid=os.getppid(),monotonic_ns=time.monotonic_ns(),
        domain=DOMAIN,RMW_IMPLEMENTATION=os.environ.get('RMW_IMPLEMENTATION'),
        signal_handler_options='NO, same as frozen headquarters; Python SIGINT untouched',
        default_Python_SIGINT=signal.getsignal(signal.SIGINT) is signal.default_int_handler,
        topic=sub.topic_name,msg_type_module=sub.msg_type.__module__,msg_type_name=sub.msg_type.__name__,raw=sub.raw))
    try:
        try:rclpy.spin(node)
        except BaseException as error:
            save(directory/'receiver-exception.json',exception_record(error))
            raise  # Preserve actual error/KeyboardInterrupt and nonzero exit.
    finally:
        begin=time.monotonic_ns()
        node.destroy_node();context.shutdown()
        save(directory/'receiver-cleanup.json',dict(begin_monotonic_ns=begin,end_monotonic_ns=time.monotonic_ns(),
            received_count=count,context_ok=context.ok(),node_destroyed=True))
    return 0


def driver(output):
    admission=json.loads(Path(__file__).with_name('ADMISSION.json').read_text())
    output.mkdir(parents=True,exist_ok=False)
    (output/'diagnostic-at-run.py').write_text(Path(__file__).read_text())
    save(output/'ADMISSION-at-run.json',admission)
    begin=time.monotonic_ns();deadline=time.monotonic()+30.
    context=Context();node=executor=process=None;sent=False;published=0;first_pub=last_pub=None
    record=dict(status='STARTED',start_monotonic_ns=begin,start_utc=datetime.now(timezone.utc).isoformat(),
        parent_pid=os.getpid(),parent_ppid=os.getppid(),domain=DOMAIN,topic=TOPIC,
        scope='No-robot real typedDDS and one SIGINT diagnostic, not original HQ/NN/Nav2/GZ/native workload or physical proof',
        planned=dict(width=WIDTH,height=HEIGHT,data_bytes=WIDTH*HEIGHT,publish_period_wall_s=PERIOD,supply_wall_s=SUPPLY_WALL,inner_wall_s=30))
    def interrupted(number,frame):raise InterruptedError(f'outer signal {number}')
    signal.signal(signal.SIGTERM,interrupted)
    try:
        command=[sys.executable,'-B',str(Path(__file__).resolve()),'--receiver-directory',str(output)]
        with (output/'receiver.stdout.txt').open('x') as stdout,(output/'receiver.stderr.txt').open('x') as stderr:
            process=subprocess.Popen(command,stdout=stdout,stderr=stderr,start_new_session=True)
        record['receiver_argv']=command;record['receiver_pid']=process.pid
        save(output/'launch.json',dict(record,launch_observed_monotonic_ns=time.monotonic_ns()))
        rclpy.init(context=context,domain_id=DOMAIN,signal_handler_options=SignalHandlerOptions.NO)
        node=Node('net01d_fixed_grid_publisher',context=context)
        executor=SingleThreadedExecutor(context=context);executor.add_node(node)
        publisher=node.create_publisher(OccupancyGrid,TOPIC,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        while not (output/'receiver-ready.json').exists() or publisher.get_subscription_count()!=1:
            if process.poll() is not None:raise RuntimeError('Receiver exited before fixed supply')
            if time.monotonic()>=deadline:raise TimeoutError('30wall startup bound')
            executor.spin_once(timeout_sec=.002)
        ready=json.loads((output/'receiver-ready.json').read_text())
        if not ready['default_Python_SIGINT']:raise RuntimeError('Receiver does not have default Python SIGINT handler')
        grid=OccupancyGrid();grid.header.frame_id='odom';grid.info.resolution=.05
        grid.info.width=WIDTH;grid.info.height=HEIGHT;grid.info.origin.orientation.w=1.
        grid.data=array('b',[0])*(WIDTH*HEIGHT)
        record['actual_CDR_bytes']=len(serialize_message(grid));record['receiver_ready']=ready
        start=time.monotonic();until=start+SUPPLY_WALL;next_publish=start
        while time.monotonic()<until:
            if process.poll() is not None:raise RuntimeError('Receiver exited before the single scheduled SIGINT')
            if time.monotonic()>=deadline:raise TimeoutError('30wall supply bound')
            now=time.monotonic()
            if now>=next_publish:
                grid.header.stamp=node.get_clock().now().to_msg();publisher.publish(grid)
                stamp=time.monotonic_ns();published+=1
                if first_pub is None:first_pub=stamp
                last_pub=stamp;next_publish+=PERIOD
            executor.spin_once(timeout_sec=min(.002,max(0.,until-time.monotonic())))
        record['signal']=dict(pid=process.pid,signal='SIGINT',before_monotonic_ns=time.monotonic_ns())
        os.kill(process.pid,signal.SIGINT);sent=True
        record['signal']['after_monotonic_ns']=time.monotonic_ns()
        save(output/'signal.json',record['signal'])
        code=process.wait(timeout=max(.001,min(5.,deadline-time.monotonic())))
        record['receiver_exit']=code
        error=json.loads((output/'receiver-exception.json').read_text()) if (output/'receiver-exception.json').exists() else None
        record['exception']=error
        matching=error is not None and error['type']=='RuntimeError' and 'Unable to convert call argument to Python object' in error['message']
        record['status']='MATCHING_RUNTIMEERROR_OBSERVED' if matching else 'NOT_REPRODUCED'
        record['observation']='Actual child exception/exit preserved; absence of one matching error in this single fixed workload is not disproof of the historical cause.'
        # Never turn a real child exception into a successful exit.
        return code if code>=0 else 128-code
    except BaseException as error:
        record.update(status='DIAGNOSTIC_FAILED_FIRST_ERROR_PRESERVED',driver_exception=exception_record(error));raise
    finally:
        if process is not None and process.poll() is None:
            record['owned_cleanup']='SIGTERM after diagnostic wait failure; no second SIGINT'
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=1)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=1)
        if executor is not None:executor.shutdown(timeout_sec=0)
        if node is not None:node.destroy_node()
        if context.ok():context.shutdown()
        record.update(end_monotonic_ns=time.monotonic_ns(),actual_published=published,
            first_publish_monotonic_ns=first_pub,last_publish_monotonic_ns=last_pub,
            actual_SIGINT_count=1 if sent else 0,actual_child_final_exit=None if process is None else process.poll(),
            owned_child_gone=process is None or process.poll() is not None,parent_context_ok=context.ok())
        save(output/'result.json',record)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path)
    parser.add_argument('--receiver-directory',type=Path);args=parser.parse_args()
    if args.receiver_directory:return receiver(args.receiver_directory)
    admission=json.loads(Path(__file__).with_name('ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True:parser.error('Inert diagnostic: Root source review/unique START required')
    return driver(args.output)


if __name__=='__main__':raise SystemExit(main())
