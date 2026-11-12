"""ZeroRobot lifecycle diagnostic; actual selected methods, explicit mock resources."""
import argparse
import ast
import gc
import json
import os
from pathlib import Path
import resource
import select
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

REPO=Path(__file__).resolve().parents[3]
SESSION=2026111151
PROFILE='net01/config/EXECUTION_PROFILE_CONTROLLED1000_CLOCK100_Q10MS_PACE10_RASTER_SIMHEALTH.json'
CASES=('closed_slow_persist_exit0','unclosed','persist_stall','saved_exit_stall')


def actual_methods():
    source=ast.parse((REPO/'net01/gateway.py').read_text())
    original=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='Gateway')
    methods=[n for n in original.body if isinstance(n,ast.FunctionDef)
        and n.name in {'poststop_phase','_close','close','persist'}]
    subject=ast.ClassDef(name='Subject',bases=[],keywords=[],body=methods,decorator_list=[])
    ns=dict(os=os,time=time,gc=gc,json=json,resource=resource)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[subject],type_ignores=[])),
        'actual Gateway methods','exec'),ns)
    return ns['Subject']


def actual_supervisor():
    source=ast.parse((REPO/'net01/run_network_case.py').read_text())
    methods=[n for n in source.body if isinstance(n,ast.FunctionDef)
        and n.name in {'gateway_closed_proof','end_gateway'}]
    ns=dict(os=os,time=time,json=json,signal=signal,controller_process=None,
        rclpy=SimpleNamespace(spin_once=lambda observer,timeout_sec:time.sleep(timeout_sec)))
    exec(compile(ast.Module(body=methods,type_ignores=[]),'actual Gateway supervisor','exec'),ns)
    return ns


def stall():
    while True:time.sleep(.05)


def child(case,directory):
    stopping=[False]
    def stop(signum,frame):stopping[0]=True
    signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
    node=actual_methods()()
    resources=[]
    def resource_event(kind):resources.append(kind)
    hub=SimpleNamespace(outgoing=[],deliveries=[],control_trace=None,
        end=(stall if case=='unclosed' else lambda:resource_event('mock_END')),
        poll=lambda:None,close=lambda:resource_event('mock_hub_close'))
    node.__dict__.update(directory=directory,session_id=SESSION,mode='B',anchor=None,failure=None,
        execution_profile=json.loads((REPO/PROFILE).read_text()),hub=hub,
        adapter_qos_events='sdk-default',central_map_captures=None,idle_phase_snapshots={'end':{}},
        python_profile=None,cpu_profile=None,main_thread_sampler=None,dispatch_stats={},records=[],
        link=SimpleNamespace(events=[]),guards={},wires=None,hub_poll_closed=False,
        control_clock_lane=False,gc_runtime={},gc_original_enabled=gc.isenabled(),gc_callback=None,
        executors=[SimpleNamespace(remove_node=lambda n:None,shutdown=lambda timeout_sec:True) for _ in range(2)],
        nodes=[SimpleNamespace(destroy_node=lambda:resource_event('mock_node_destroy')) for _ in range(2)],
        contexts=[SimpleNamespace(shutdown=lambda:resource_event('mock_context_shutdown')) for _ in range(2)])
    if case=='closed_slow_persist_exit0':
        real_persist=node.persist
        def delayed_persist():time.sleep(22);real_persist()
        node.persist=delayed_persist
    elif case=='persist_stall':
        # Actual persist enters its first passive-capture hook and blocks there.
        node.central_map_captures=[];node.persist_central_maps=stall
    print('READY',flush=True)
    while not stopping[0]:time.sleep(.005)
    clean=node.close()  # actual close -> actual _close -> actual persist
    if case=='saved_exit_stall':stall()
    node.poststop_phase('fixture_child_main_return',exit_code=0 if clean else 1,
        mock_resource_calls=resources)
    return 0 if clean else 1


def observer(directory,hard_deadline_ns):
    rows=[]
    o=SimpleNamespace(directory=directory,gateway_evidence_wall_s=60,
        gateway_evidence_eligible=True,authority_stopped=True,gateway_cleanup_deadline_ns=time.monotonic_ns()+90_000_000_000,
        gateway_hard_deadline_ns=hard_deadline_ns,gateway_shutdown_started_ns=None,
        event=lambda kind,**fields:rows.append(dict(kind=kind,observed_monotonic_ns=time.monotonic_ns(),**fields)),
        stop_zeros=lambda:None)
    return o,rows


def short_checks(directory):
    # Command construction is the real host assignment, not a second oracle.
    tree=ast.parse((REPO/'net01/host_run.py').read_text())
    assign=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='runner_command' for t in n.targets))
    for controlled,deadline,expected in [(None,None,False),(True,None,False),(True,123.0,True)]:
        ns=dict(controlled=None if controlled is None else SimpleNamespace(python_command=lambda args:args),
            HERE=REPO/'net01',relative=Path('example.ready.json'),host_deadline=deadline)
        exec(compile(ast.Module(body=[assign],type_ignores=[]),'actual runner command','exec'),ns)
        assert ('--host-hard-deadline-ns' in ns['runner_command']) is expected
    # Invalid proof rejection uses the actual reader, with no signal or process.
    ns=actual_supervisor();pid=999999
    proof=dict(phase='resources_closed',safe_closed=True,pid=pid,session_id=SESSION,
        case=str(directory.resolve()),monotonic_ns=110_000_000_000,
        cleanup=dict(resources_destroyed=True,end_frame_flushed=True,executor_shutdown=[True,True],
            unresolved_C_RPC=[],unresolved_R_RPC=[],unresolved_local_cleanup_futures={'1':0,'2':0,'3':0}))
    process=SimpleNamespace(pid=pid)
    path=directory/'network-gateway-resources-closed.json'
    assert ns['gateway_closed_proof'](process,SimpleNamespace(directory=directory),100_000_000_000,120_000_000_000) is None
    path.write_text(json.dumps(proof))
    assert ns['gateway_closed_proof'](process,SimpleNamespace(directory=directory),100_000_000_000,120_000_000_000)
    for key,bad in [('pid',pid+1),('session_id',SESSION+1),('case','/other-case'),('monotonic_ns',99_000_000_000)]:
        path.write_text(json.dumps(dict(proof,**{key:bad})))
        assert ns['gateway_closed_proof'](process,SimpleNamespace(directory=directory),100_000_000_000,120_000_000_000) is None
    path.unlink()
    # Pure FSM time injection: no real signals, no claim of real wall timing.
    for tight in (False,True):
        now=[100_000_000_000];sent=[];rows=[]
        fake_time=SimpleNamespace(monotonic_ns=lambda:now[0])
        fake_os=SimpleNamespace(environ={'NET01_SESSION_ID':str(SESSION)},
            killpg=lambda pid,sig:sent.append((now[0],sig.name)))
        ns=actual_supervisor();ns.update(time=fake_time,os=fake_os,
            rclpy=SimpleNamespace(spin_once=lambda obs,timeout_sec:now.__setitem__(0,now[0]+max(1,int(timeout_sec*1e9)))))
        hard=now[0]+(4 if tight else 900)*1_000_000_000
        o=SimpleNamespace(directory=directory,gateway_evidence_wall_s=60,gateway_evidence_eligible=False,
            authority_stopped=True,gateway_cleanup_deadline_ns=now[0]+90_000_000_000,
            gateway_hard_deadline_ns=hard,gateway_shutdown_started_ns=None,
            event=lambda kind,**fields:rows.append(dict(kind=kind,**fields)),stop_zeros=lambda:None)
        process=SimpleNamespace(pid=pid,poll=lambda:None)
        ns['end_gateway'](process,o)
        baseline=o.gateway_shutdown_started_ns;first_end=now[0]
        ns['end_gateway'](process,o)
        assert o.gateway_shutdown_started_ns==baseline
        assert now[0]==first_end and now[0]<=hard
        supervision=[r for r in rows if r['kind']=='gateway_poststop_supervision']
        assert supervision[0]['begin_monotonic_ns']==supervision[1]['begin_monotonic_ns']
        assert not any(r['kind']=='gateway_evidence_grace' for r in rows)
    return dict(host_actual_command_branches=3,invalid_marker_cases=['missing','stale_PID','session','case','old_monotonic'],
        default_no_extension_and_reentry_FSM=True,short_parent_bound_FSM=True,
        scope='Actual extracted functions with injected clocks/signals, NOT real wall/ROS/physical proof')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--child',choices=CASES)
    args=parser.parse_args()
    if args.child:return child(args.child,args.directory)
    admission=json.loads(Path(__file__).with_name('ADMISSION.json').read_text())
    if admission['execution_authorized'] is not True:parser.error('Inert fixture: Root execution admission required')
    def interrupted(signum,frame):raise KeyboardInterrupt('fixture outer signal')
    signal.signal(signal.SIGTERM,interrupted)
    directory=args.directory.resolve();directory.mkdir(parents=True,exist_ok=False)
    os.environ['NET01_SESSION_ID']=str(SESSION)
    result=dict(status='STARTED',scope='ZeroRobot mock resources; actual close/persist/supervisor, no ROS/ns3/GZ',cases=[])
    try:
        snapshots=directory/'source-at-run';snapshots.mkdir()
        (snapshots/'check-at-run.py').write_text(Path(__file__).read_text())
        (snapshots/'ADMISSION.json').write_text(Path(__file__).with_name('ADMISSION.json').read_text())
        for relative in ['net01/gateway.py','net01/run_network_case.py','net01/host_run.py',PROFILE]:
            (snapshots/Path(relative).name).write_text((REPO/relative).read_text())
        checks=directory/'short-checks';checks.mkdir();result['short_checks']=short_checks(checks)
        for case in CASES:
            out=directory/case;out.mkdir();begin=time.monotonic_ns();hard=begin+65_000_000_000
            argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--directory',str(out),'--child',case]
            with (out/'child.log').open('x') as log:
                process=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=log,text=True,start_new_session=True)
                rows=[]
                try:
                    readable,_,_=select.select([process.stdout],[],[],5)
                    if not readable or process.stdout.readline().strip()!='READY':raise RuntimeError('child not ready')
                    subject,rows=observer(out,hard);ns=actual_supervisor()
                    ns['end_gateway'](process,subject)
                    code=process.wait(timeout=max(.001,(hard-time.monotonic_ns())/1e9))
                finally:
                    if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait()
                    (out/'supervisor.json').write_text(json.dumps(rows,indent=2)+'\n')
            elapsed=(time.monotonic_ns()-begin)/1e9
            marker=out/'network-gateway-resources-closed.json';saved=out/'network-gateway-saved.json'
            grace=any(r['kind']=='gateway_evidence_grace' for r in rows)
            phases=[json.loads(line)['phase'] for line in (out/'network-gateway-close-phases.jsonl').read_text().splitlines()]
            row=dict(case=case,argv=argv,pid=process.pid,exit=code,wall_s=elapsed,
                resources_marker=marker.exists(),saved=saved.exists(),extension=grace,phases=phases,
                supervisor='supervisor.json',owned_gone=not Path('/proc/'+str(process.pid)).exists())
            result['cases'].append(row)
            assert row['owned_gone'] and elapsed<65
            if case=='closed_slow_persist_exit0':assert code==0 and saved.exists() and grace and 22<=elapsed<35
            elif case=='unclosed':assert code==-signal.SIGKILL and not marker.exists() and not grace and 24<=elapsed<35
            else:
                assert code==-signal.SIGKILL and marker.exists() and grace and 54<=elapsed<65
                assert saved.exists() is (case=='saved_exit_stall')
        result['status']='PASS_ZERO_ROBOT_LIFECYCLE_ONLY'
    except BaseException as error:
        result.update(status='FAIL_FIRST_ERROR_PRESERVED',error=repr(error));raise
    finally:(directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
