"""Resident public administrative client, not a business path or state injector.

Only a host proof of actual client exit0 and three real terminal results permits
one SetBool(true) request to the original stop_observe service.
"""
import argparse
import json
from pathlib import Path
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--trigger-file',type=Path,required=True)
    parser.add_argument('--ack-file',type=Path,required=True)
    parser.add_argument('--stop-file',type=Path,required=True)
    parser.add_argument('--work-deadline-ns',type=int,required=True)
    args=parser.parse_args(); args.directory.mkdir(exist_ok=False)
    import rclpy
    from rclpy.node import Node
    from rclpy.signals import SignalHandlerOptions
    from std_srvs.srv import SetBool
    rclpy.init(domain_id=92,signal_handler_options=SignalHandlerOptions.NO)
    node=Node('net01e_normal_stop_control')
    client=node.create_client(SetBool,'/net01/time_control/stop_observe')
    result=dict(operation=None,authority_proof=None,response=None,error=None)
    try:
        print('NORMAL_STOP_CONTROL_READY',flush=True)
        while not args.stop_file.exists() and not args.trigger_file.exists():
            if time.monotonic_ns()>=args.work_deadline_ns:
                raise TimeoutError('Original work deadline before authority proof')
            rclpy.spin_once(node,timeout_sec=.001)
        if args.stop_file.exists():
            result['stopped_without_authority_request']=True
            return 0
        proof=json.loads(args.trigger_file.read_text())
        if (proof['client_exit']!=0 or proof['actual_results']!={'tb1':4,'tb2':4,'tb3':5}
                or not proof['normal_done']):
            raise ValueError('No actual normal authority-exit proof')
        result['authority_proof']=proof
        if not client.service_is_ready():
            raise RuntimeError('Original stop_observe service not discovered by resident client')
        requested=time.monotonic_ns()
        future=client.call_async(SetBool.Request(data=True))
        result['operation']=dict(name='stop_observe',data=True,request_monotonic_ns=requested)
        call_deadline=min(args.work_deadline_ns,requested+2_000_000_000)
        while not future.done():
            if time.monotonic_ns()>=call_deadline:
                raise TimeoutError('Actual stop_observe response not received within2wall/work bound')
            rclpy.spin_once(node,timeout_sec=.001)
        response=future.result(); state=json.loads(response.message)
        result['response']=dict(success=response.success,state=state,monotonic_ns=time.monotonic_ns())
        if (not response.success or state['session_id']!=2026110912 or not state['authority_exited']
                or state['failure'] is not None or state['mode']!='STOP_COUPLED'):
            raise RuntimeError('Original stop_observe did not confirm same-session normal authority exit')
        args.ack_file.write_text(json.dumps(result['response'])+'\n')
        return 0
    except BaseException as error:
        result['error']=repr(error); raise
    finally:
        (args.directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        node.destroy_node(); rclpy.shutdown()


if __name__=='__main__':
    raise SystemExit(main())
