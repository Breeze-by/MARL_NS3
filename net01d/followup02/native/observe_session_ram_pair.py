"""Separately admitted fixed serial/RAM pair; original stream runner is reused."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from observe_lto_pair import proc,owned_tree,MODULES,REPO,WORKSPACE,BASE

LIBRARIES=WORKSPACE/'net-01d/ns3-lto-portable-followup02/build/lib'
REFERENCE=WORKSPACE/'net-01d/ns3-lto-portable-followup02/driver-out/net01-payload-tcp'
def main(arm,candidate_native=None):
    reference=arm=='reference';name='ntcp-ram-r1' if reference else 'ntcp-ram-c1'
    if not reference and candidate_native is None:raise ValueError('Explicit candidate artifact required')
    binary=REFERENCE if reference else candidate_native
    folder=BASE/'native/session-ram-pair-01'/arm
    output=BASE/'runs'/name;ram=Path('/dev/shm')/('net01d-f02-'+name)
    if not reference:
        prior=json.loads((folder.parent/'reference/wrapper-result.json').read_text())
        if prior['status']!='PASS_LOADED_NATIVE_BYTE_SCOPE':
            raise RuntimeError('Reference failed; candidate not started')
    for path in (binary,LIBRARIES,Path('/usr/bin/time')):
        if not path.exists():raise FileNotFoundError(path)
    if output.exists() or ram.exists() or folder.exists():raise FileExistsError('Exclusive pair identity exists')
    if len(os.fsencode(output/'wire.sock'))>=108:raise ValueError('Host Unix socket path too long')
    folder.mkdir(parents=True,exist_ok=False)
    started=time.monotonic_ns();deadline=started+60_000_000_000
    time_file=folder/'time-v.txt'
    command=['/usr/bin/time','-v','-o',str(time_file),'timeout','--signal=TERM','--kill-after=2s','60s',
        'python3','-B','net01d/followup02/native/run_native_tcp.py','--case','stream-01',
        '--output-name',name,'--native-transport','tcp-mtu-v2','--native',str(binary),
        '--native-ledger-mode','serial' if reference else 'session-ram-v1',
        '--finalize-hard-deadline-ns',str(deadline)]
    env=os.environ.copy()
    for key in ('LD_PRELOAD','LD_AUDIT'):env.pop(key,None)
    env['LD_LIBRARY_PATH']=str(LIBRARIES)
    result=dict(arm=arm,status='NOT_STARTED',argv=command,cwd=str(REPO),native=str(binary),
        environment=dict(LD_LIBRARY_PATH=str(LIBRARIES),LD_PRELOAD='UNSET',LD_AUDIT='UNSET'),
        output=str(output),RAM=str(ram),whole_deadline_monotonic_ns=deadline,whole_wall_bound_s=60,
        internal_bounds='Original active20/ENDflush<=1/Hub active25; only explicit runner post-END wait uses remaining absolute60. Serial Hub native wait10 unchanged; RAM finalize min(END+90,absolute60).',
        time_v_file=str(time_file),
        time_scope='Runner and waited subtree CPU/wall, including Hub/native END/copy/ledger summary; observer parent CPU excluded.',
        observation_scope='10ms owned-tree discovery until one native READY/maps capture; no further runtime sampling')
    process=None;seen={};observation=None
    with (folder/'argv.json').open('x') as stream:json.dump(command,stream,indent=2)
    with (folder/'environment.json').open('x') as stream:json.dump(result['environment'],stream,indent=2)
    stdout=(folder/'stdout.log').open('x');stderr=(folder/'stderr.log').open('x')
    try:
        process=subprocess.Popen(command,cwd=REPO,env=env,stdout=stdout,stderr=stderr)
        result.update(status='RUNNING',time_pid=process.pid)
        (folder/'owner.json').write_text(json.dumps(proc(process.pid),indent=2)+'\n')
        while process.poll() is None:
            tree=owned_tree(process.pid);seen.update(tree)
            matches=[r for r in tree.values() if r['argv'] and r['argv'][0]==str(binary)]
            if len(matches)>1:raise RuntimeError('Multiple matching owned native children')
            if matches and (output/'wire.sock').exists():
                row=matches[0];begin=time.monotonic_ns();root=Path('/proc')/str(row['pid'])
                maps=root.joinpath('maps').read_text();executable=os.readlink(root/'exe')
                (folder/'native.maps.txt').write_text(maps)
                mapped={line.split(None,5)[5] for line in maps.splitlines()
                    if len(line.split(None,5))==6 and Path(line.split(None,5)[5]).name.startswith('libns3.40-')}
                expected={'libns3.40-'+module+'.so' for module in MODULES}
                chain=[];cursor=row['pid']
                while cursor in tree:chain.append(tree[cursor]);cursor=tree[cursor]['ppid']
                observation=dict(native=row,ancestry_native_to_time=chain,exe=executable,
                    begin_monotonic_ns=begin,end_monotonic_ns=time.monotonic_ns(),mapped_ns3_paths=sorted(mapped),
                    expected_names=sorted(expected),actual13_names={Path(p).name for p in mapped}==expected,
                    all_in_expected_root=bool(mapped) and all(Path(p).resolve().parent==LIBRARIES.resolve() for p in mapped),
                    exact_native_executable=Path(executable).resolve()==binary.resolve(),
                    runner_and_Hub_in_owned_chain=any('net01d/followup02/native/run_native_tcp.py' in r['argv'] for r in chain)
                        and any(str(REPO/'net01/tools/packet_hub.py') in r['argv'] for r in chain),
                    actual_time_root_in_chain=process.pid in {r['pid'] for r in chain})
                (folder/'native-observation.json').write_text(json.dumps(observation,indent=2)+'\n')
                break
            time.sleep(.01)
    except Exception as error:result.update(status='FAIL',first_error=repr(error))
    finally:
        if process is not None:
            result['time_exit']=process.wait();result['subtree_exit_monotonic_ns']=time.monotonic_ns()
        stdout.close();stderr.close()
        remaining=[]
        for pid,row in seen.items():
            try:
                current=proc(pid)
                if current['start_ticks']==row['start_ticks']:remaining.append(current)
            except (FileNotFoundError,ProcessLookupError):pass
        result.update(wall_s=(time.monotonic_ns()-started)/1e9,remaining_observed_owned=remaining,observation=observation)
        result['original_byte_resource_pass']=False
        raw=output/'result.json'
        if raw.exists():
            try:
                runner=json.loads(raw.read_text());resources=runner['resources'];hub=runner.get('raw_Hub_result',{})
                result['runner_small']=dict(status=runner['status'],first_error=runner.get('first_error'),
                    wall_s=runner['wall_s'],resources=resources,native_exit=hub.get('native_exit'),Hub_status=hub.get('status'),
                    native_storage=hub.get('native_evidence_storage'),poststop_finalize=hub.get('poststop_finalize'))
                result['original_byte_resource_pass']=(runner['status']=='PASS_NATIVE_BYTES_ONLY'
                    and resources['hub_exit']==0 and hub.get('status')=='PASS' and hub.get('native_exit')==0
                    and hub.get('native_evidence_storage',{}).get('complete') is True
                    and not resources['forced_signals'] and not resources['remaining_owned_native'])
            except (ValueError,KeyError) as error:
                result.update(status='FAIL',runner_evidence_error=repr(error))
                result.setdefault('first_error','Original runner evidence incomplete after exit')
        result['acceptance_monotonic_ns']=time.monotonic_ns()
        result['whole_deadline_met']=result['acceptance_monotonic_ns']<deadline
        if result['status']!='FAIL':
            valid=observation is not None and all(observation[k] for k in ('actual13_names','all_in_expected_root',
                'exact_native_executable','runner_and_Hub_in_owned_chain','actual_time_root_in_chain'))
            if (not valid or result.get('time_exit')!=0 or not time_file.is_file()
                    or not result['original_byte_resource_pass'] or remaining or not result['whole_deadline_met']):
                result.update(status='FAIL',first_error='Original bytes/resource, maps/owned-chain, exit or absolute60 proof failed')
            else:result['status']='PASS_LOADED_NATIVE_BYTE_SCOPE'
        with (folder/'wrapper-result.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
        print(json.dumps(dict(arm=arm,status=result['status'],first_error=result.get('first_error'),
            time_exit=result.get('time_exit'),wall_s=result['wall_s'],evidence=str(folder))),flush=True)
    return 0 if result['status']=='PASS_LOADED_NATIVE_BYTE_SCOPE' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--arm',choices=('reference','candidate'),required=True)
    parser.add_argument('--candidate-native',type=Path,help='Root-fixed candidate artifact; required for candidate arm')
    args=parser.parse_args()
    raise SystemExit(main(args.arm,args.candidate_native))
