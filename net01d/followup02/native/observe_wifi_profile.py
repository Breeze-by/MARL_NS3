"""One separately admitted Wi-Fi DSO profile, using the original stream runner."""
import json
import os
from pathlib import Path
import subprocess
import time

from observe_lto_pair import proc,owned_tree,MODULES,REPO,WORKSPACE,BASE

BINARY=WORKSPACE/'net-01d/ns3-lto-portable-followup02/driver-out/net01-payload-tcp'
LIBRARIES=WORKSPACE/'net-01d/ns3-lto-portable-followup02/build/lib'
EXEC=BASE/'native/native_profile_wifi_exec.py'
FOLDER=BASE/'native/wifi-profile-01'
OUTPUT=BASE/'runs/ntcp-prof-wifi-01'
RAM=Path('/dev/shm/net01d-f02-ntcp-prof-wifi-01')


def profile_products(deadline):
    profile=FOLDER/'ld-profile/libns3.40-wifi.so.profile'
    commands=[]
    for option,name in (('-p','flat'),('-c','call-pairs')):
        command=['/usr/bin/sprof',option,str(LIBRARIES/'libns3.40-wifi.so'),str(profile)]
        with (FOLDER/f'sprof-{name}.txt').open('xb') as stdout, (FOLDER/f'sprof-{name}.stderr.txt').open('xb') as stderr:
            completed=subprocess.run(command,stdout=stdout,stderr=stderr,
                timeout=max(0.,(deadline-time.monotonic_ns())/1e9))
        commands.append(dict(argv=command,exit=completed.returncode))
    with (OUTPUT/'hub/native-control-boundaries.json').open() as stream:boundaries=json.load(stream)
    begins={r['horizon_ns']:r for r in boundaries if r['kind']=='cpu_step_begin'}
    ends={r['horizon_ns']:r for r in boundaries if r['kind']=='cpu_step_end'}
    own={}
    for horizon in begins.keys()&ends.keys():
        for category,total in ends[horizon]['cumulative_cpu'].items():
            target=own.setdefault(category,dict(calls=0,inclusive_ns=0,exclusive_ns=0))
            for key in target:target[key]+=total[key]-begins[horizon]['cumulative_cpu'][category][key]
    with (OUTPUT/'hub/native/control-step-trace.jsonl').open() as stream:steps=[json.loads(line) for line in stream]
    pcaps=[]
    for node in range(4):
        name=f'wifi-{node}-0.pcap'
        actual=(OUTPUT/'hub/native'/name).read_bytes()
        reference=(BASE/'runs/ntcp-ram-r1/hub/native'/name).read_bytes()
        pcaps.append(dict(file=name,actual_bytes=len(actual),reference_bytes=len(reference),exact=actual==reference))
    return dict(profile_file=str(profile),profile_bytes=profile.stat().st_size,sprof=commands,
        matched_CPU_boundary_horizons=len(begins.keys()&ends.keys()),own_callback_Run_CPU=own,
        measured_Run_CPU_ns=sum(r['end_thread_cpu_ns']-r['begin_thread_cpu_ns'] for r in steps),
        measured_Run_wall_ns=sum(r['end_monotonic_ns']-r['begin_monotonic_ns'] for r in steps),
        PCAP_against_saved_serial_reference=pcaps,
        semantics='sprof is selected-DSO samples/exported call pairs, not full native CPU. Own callback inclusive parents overlap; exclusive scopes cover only instrumented categories. Run/whole timings contain profiling overhead.')


def main():
    for path in (BINARY,LIBRARIES,EXEC,Path('/usr/bin/time'),Path('/usr/bin/sprof')):
        if not path.exists():raise FileNotFoundError(path)
    if FOLDER.exists() or OUTPUT.exists() or RAM.exists():raise FileExistsError('Exclusive Wi-Fi profile identity exists')
    if len(os.fsencode(OUTPUT/'wire.sock'))>=108:raise ValueError('Host Unix socket path too long')
    FOLDER.mkdir();(FOLDER/'ld-profile').mkdir()
    started=time.monotonic_ns();deadline=started+60_000_000_000
    command=['/usr/bin/time','-v','-o',str(FOLDER/'time-v.txt'),'timeout','--signal=TERM','--kill-after=2s','60s',
        'python3','-B','net01d/followup02/native/run_native_tcp.py','--case','stream-01',
        '--output-name','ntcp-prof-wifi-01','--native-transport','tcp-mtu-v2','--native',str(EXEC),
        '--native-ledger-mode','serial','--finalize-hard-deadline-ns',str(deadline)]
    env=os.environ.copy()
    for key in ('LD_PROFILE','LD_PROFILE_OUTPUT','LD_PRELOAD','LD_AUDIT'):env.pop(key,None)
    env['LD_LIBRARY_PATH']=str(LIBRARIES)
    result=dict(status='NOT_STARTED',argv=command,cwd=str(REPO),whole_deadline_ns=deadline,
        parent_child_environment={k:env.get(k) for k in ('LD_LIBRARY_PATH','LD_PROFILE','LD_PROFILE_OUTPUT','LD_PRELOAD','LD_AUDIT')},
        native_exec_wrapper=str(EXEC),real_native=str(BINARY),profiled_DSO='libns3.40-wifi.so',
        time_scope='GNU time original runner+waited children incl END/copy/summary; excludes later sprof/PCAP analysis, which must still fit same whole60.',
        bounds='active20,ENDflush<=1/start22,Hubactive25,serialnativeENDwait10; explicit test runner post-END wait uses same remaining absolutewhole60; no fresh60.')
    (FOLDER/'argv.json').write_text(json.dumps(command,indent=2)+'\n')
    (FOLDER/'observer-source.py').write_bytes(Path(__file__).read_bytes())
    for name,path in (('source-runner.py',BASE/'native/run_native_tcp.py'),
                      ('source-Hub.py',REPO/'net01/tools/packet_hub.py'),
                      ('source-loader-helper.py',BASE/'native/observe_lto_pair.py')):
        (FOLDER/name).write_bytes(path.read_bytes())
    process=None;seen={};observation=None
    with (FOLDER/'stdout.log').open('x') as stdout,(FOLDER/'stderr.log').open('x') as stderr:
        try:
            process=subprocess.Popen(command,cwd=REPO,env=env,stdout=stdout,stderr=stderr)
            (FOLDER/'owner.json').write_text(json.dumps(proc(process.pid),indent=2)+'\n')
            while process.poll() is None:
                tree=owned_tree(process.pid);seen.update(tree)
                matches=[r for r in tree.values() if r['argv'] and r['argv'][0]==str(BINARY)]
                if len(matches)>1:raise RuntimeError('Multiple owned matching natives')
                if matches and (OUTPUT/'wire.sock').exists():
                    row=matches[0];root=Path('/proc')/str(row['pid']);maps=root.joinpath('maps').read_text()
                    (FOLDER/'native.maps.txt').write_text(maps)
                    fields=[line.split(None,5) for line in maps.splitlines()]
                    mapped={r[5] for r in fields if len(r)==6 and Path(r[5]).name.startswith('libns3.40-')}
                    environment={}
                    non_native_profile=[]
                    for pid in tree:
                        values=dict(os.fsdecode(v).split('=',1) for v in (Path('/proc')/str(pid)/'environ').read_bytes().split(b'\0') if b'=' in v)
                        if pid==row['pid']:environment={k:values.get(k) for k in ('LD_LIBRARY_PATH','LD_PROFILE','LD_PROFILE_OUTPUT','LD_PRELOAD','LD_AUDIT')}
                        elif values.get('LD_PROFILE'):non_native_profile.append(dict(pid=pid,LD_PROFILE=values['LD_PROFILE']))
                    chain=[];cursor=row['pid']
                    while cursor in tree:chain.append(tree[cursor]);cursor=tree[cursor]['ppid']
                    observation=dict(native=row,exe=os.readlink(root/'exe'),ancestry_native_to_time=chain,
                        mapped_ns3_paths=sorted(mapped),actual13={Path(p).name for p in mapped}=={'libns3.40-'+m+'.so' for m in MODULES},
                        same_library_root=bool(mapped) and all(Path(p).resolve().parent==LIBRARIES.resolve() for p in mapped),
                        native_environment=environment,other_profiled_owned_processes=non_native_profile,
                        actual_time_root_in_chain=process.pid in {r['pid'] for r in chain},
                        original_runner_and_Hub=any('net01d/followup02/native/run_native_tcp.py' in r['argv'] for r in chain)
                            and any(str(REPO/'net01/tools/packet_hub.py') in r['argv'] for r in chain))
                    (FOLDER/'native-observation.json').write_text(json.dumps(observation,indent=2)+'\n')
                    break
                time.sleep(.01)
        except Exception as error:result.update(status='FAIL',first_error=repr(error))
        finally:
            if process is not None:result['time_exit']=process.wait()
    remaining=[]
    for pid,row in seen.items():
        try:
            current=proc(pid)
            if current['start_ticks']==row['start_ticks']:remaining.append(current)
        except (FileNotFoundError,ProcessLookupError):pass
    result.update(observation=observation,remaining_observed_owned=remaining)
    try:
        runner=json.loads((OUTPUT/'result.json').read_text());hub=runner['raw_Hub_result']
        result['original_runner_result']=dict(status=runner['status'],resources=runner['resources'],checks=runner['checks'],received=len(runner['received']))
        result['whole_time_v']=(FOLDER/'time-v.txt').read_text()
        if result['status']!='FAIL':
            products=profile_products(deadline);result['profile_products']=products
            valid=(result['time_exit']==0 and runner['status']=='PASS_NATIVE_BYTES_ONLY' and hub['status']=='PASS'
                and hub['native_exit']==0 and hub['native_evidence_storage']['complete'] and not remaining
                and observation is not None and observation['exe']==str(BINARY) and observation['actual13'] and observation['same_library_root']
                and observation['actual_time_root_in_chain'] and observation['original_runner_and_Hub']
                and observation['native']['argv'][-1]=='--cpuProfile=1' and observation['native_environment']['LD_PROFILE']=='libns3.40-wifi.so'
                and observation['native_environment']['LD_PROFILE_OUTPUT']==str(FOLDER/'ld-profile') and not observation['other_profiled_owned_processes']
                and products['profile_bytes']>0 and all(r['exit']==0 for r in products['sprof'])
                and products['matched_CPU_boundary_horizons']==800 and all(r['exact'] for r in products['PCAP_against_saved_serial_reference'])
                and time.monotonic_ns()<deadline)
            result['status']='PASS_PROFILE_CAPTURE_NATIVE_BYTE_SCOPE' if valid else 'FAIL'
    except Exception as error:result.update(status='FAIL',first_error=result.get('first_error',repr(error)))
    result['whole_elapsed_s']=(time.monotonic_ns()-started)/1e9
    (FOLDER/'wrapper-result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],first_error=result.get('first_error'),evidence=str(FOLDER))),flush=True)
    return 0 if result['status']=='PASS_PROFILE_CAPTURE_NATIVE_BYTE_SCOPE' else 1


if __name__=='__main__':raise SystemExit(main())
