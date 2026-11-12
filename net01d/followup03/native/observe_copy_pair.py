"""One-time maps/owned observation around one separately admitted original stream arm."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'net01d/followup02/native'))
from observe_lto_pair import proc,owned_tree,MODULES
BASE=REPO/'net01d/followup03'
WS=REPO.parents[1]
LIBRARIES=WS/'net-01d/ns3-lto-portable-followup02/build/lib'
REFERENCE=WS/'net-01d/ns3-lto-portable-followup02/driver-out/net01-payload-tcp'
CANDIDATE=WS/'net-01d/native-copy-cost-followup03/driver-out/net01-payload-tcp'

def main(arm, *, cpu_clean=False, pcap_shim=False):
    admission_path=(BASE/'native/pcap-cpu-shim-01/ADMISSION.json' if pcap_shim else
        BASE/'native/cpu-clean-01/ADMISSION.json' if cpu_clean else BASE/'TCP_COPY_PAIR_ADMISSION.json')
    admission=json.loads(admission_path.read_text())
    if admission['execution_authorized'] is not True:raise RuntimeError('Root pair admission is pending')
    name=('ntcp-pcap-cpu-01' if pcap_shim else 'ntcp-cpu-clean-01' if cpu_clean
          else 'ntcp-copy-r1' if arm=='reference' else 'ntcp-copy-c1')
    binary=REFERENCE if arm=='reference' else CANDIDATE
    folder=(BASE/'native/pcap-cpu-shim-01/capture' if pcap_shim else
        BASE/'native/cpu-clean-01/capture' if cpu_clean else BASE/'native/copy-pair-01'/arm)
    output=BASE/'runs'/name
    ram=Path('/dev/shm')/('net01d-f02-'+name)
    if arm=='candidate' and not cpu_clean and not pcap_shim:
        prior=json.loads((folder.parent/'reference/wrapper-result.json').read_text())
        if prior['status']!='PASS_LOADED_NATIVE_BYTE_SCOPE':raise RuntimeError('Reference failed; candidate not started')
    for path in (binary,LIBRARIES,Path('/usr/bin/time')):
        if not path.exists():raise FileNotFoundError(path)
    if any(x.exists() for x in (folder,output,ram)):raise FileExistsError('Exclusive pair path already exists')
    folder.mkdir(parents=True)
    timefile=folder/'time-v.txt'
    entry=(['net01d/followup03/native/pcap-cpu-shim-01/run_case.py'] if pcap_shim else
           ['net01d/followup03/native/cpu-clean-01/run_case.py'] if cpu_clean else
           ['net01d/followup03/native/run_copy_pair_arm.py','--arm',arm])
    command=['/usr/bin/time','-v','-o',str(timefile),'timeout','--signal=TERM','--kill-after=2s','30s',
             'python3','-B',*entry]
    env=os.environ.copy()
    for key in ('LD_PRELOAD','LD_AUDIT','LD_PROFILE','LD_PROFILE_OUTPUT'):env.pop(key,None)
    env['LD_LIBRARY_PATH']=str(LIBRARIES)
    result=dict(arm=arm,status='NOT_STARTED',argv=command,native=str(binary),output=str(output),RAM=str(ram),
        environment={k:env.get(k) for k in ('LD_LIBRARY_PATH','LD_PRELOAD','LD_AUDIT','LD_PROFILE','LD_PROFILE_OUTPUT')},
        time_scope='Runner and waited Hub/native subtree, including TX outside Run/END/copy/summary; not pure native Run CPU',
        observation_scope='10ms owned-tree discovery until first READY socket/maps only; no ongoing sampling',
        active_wall_s=20,whole_wall_s=30)
    (folder/'argv.json').write_text(json.dumps(command,indent=2)+'\n')
    child=None;seen={};observed=None;started=time.monotonic()
    with (folder/'stdout.log').open('x') as stdout,(folder/'stderr.log').open('x') as stderr:
        try:
            child=subprocess.Popen(command,cwd=REPO,env=env,stdout=stdout,stderr=stderr)
            (folder/'owner.json').write_text(json.dumps(proc(child.pid),indent=2)+'\n')
            while child.poll() is None:
                tree=owned_tree(child.pid);seen.update(tree)
                matches=[r for r in tree.values() if r['argv'] and r['argv'][0]==str(binary)]
                if len(matches)>1:raise RuntimeError('Multiple owned matching native children')
                if matches and (output/'wire.sock').exists():
                    row=matches[0];begin=time.monotonic_ns();root=Path('/proc')/str(row['pid'])
                    maps=root.joinpath('maps').read_text();exe=os.readlink(root/'exe')
                    (folder/'native.maps.txt').write_text(maps)
                    mapped={line.split(None,5)[5] for line in maps.splitlines() if len(line.split(None,5))==6
                            and Path(line.split(None,5)[5]).name.startswith('libns3.40-')}
                    chain=[];cursor=row['pid']
                    while cursor in tree:chain.append(tree[cursor]);cursor=tree[cursor]['ppid']
                    expected={'libns3.40-'+m+'.so' for m in MODULES}
                    observed=dict(native=row,exe=exe,ancestry_native_to_time=chain,mapped_ns3_paths=sorted(mapped),
                        begin_monotonic_ns=begin,end_monotonic_ns=time.monotonic_ns(),
                        exact13_names={Path(x).name for x in mapped}==expected,
                        all_in_expected_root=bool(mapped) and all(Path(x).resolve().parent==LIBRARIES.resolve() for x in mapped),
                        exact_native_executable=Path(exe).resolve()==binary.resolve(),
                        native_parent_is_Hub=any(r['pid']==row['ppid'] and str(REPO/'net01/tools/packet_hub.py') in r['argv'] for r in chain),
                        actual_time_root_in_chain=child.pid in {r['pid'] for r in chain})
                    if cpu_clean or pcap_shim:
                        values=dict(os.fsdecode(v).split('=',1) for v in root.joinpath('environ').read_bytes().split(b'\0') if b'=' in v)
                        observed['native_environment']={k:values.get(k) for k in ('LD_LIBRARY_PATH','LD_PROFILE','LD_PROFILE_OUTPUT','LD_PRELOAD','LD_AUDIT')}
                        if cpu_clean:
                            observed['cpu_clean_exec_verified']=(row['argv'].count('--cpuProfile=1')==1
                                and all(values.get(k) is None for k in ('LD_PROFILE','LD_PROFILE_OUTPUT','LD_PRELOAD','LD_AUDIT')))
                        if pcap_shim:
                            shim=str(BASE/'native/pcap-cpu-shim-01/pcap_cpu_shim.so')
                            observed['shim_mapped']=any(len(parts:=line.split(None,5))==6 and parts[5]==shim for line in maps.splitlines())
                            observed['ancestor_LD_PRELOAD']={}
                            for parent in chain[1:]:
                                entries=dict(os.fsdecode(v).split('=',1) for v in (Path('/proc')/str(parent['pid'])/'environ').read_bytes().split(b'\0') if b'=' in v)
                                observed['ancestor_LD_PRELOAD'][str(parent['pid'])]=entries.get('LD_PRELOAD')
                            observed['observer_LD_PRELOAD']=os.environ.get('LD_PRELOAD')
                            observed['pcap_shim_exec_verified']=(observed['shim_mapped'] and values.get('LD_PRELOAD')==shim
                                and values.get('LD_LIBRARY_PATH')==str(LIBRARIES)
                                and not any(arg.startswith('--cpuProfile') for arg in row['argv'])
                                and all(values.get(k) is None for k in ('LD_PROFILE','LD_PROFILE_OUTPUT','LD_AUDIT'))
                                and all(v is None for v in observed['ancestor_LD_PRELOAD'].values())
                                and observed['observer_LD_PRELOAD'] is None)
                    (folder/'native-observation.json').write_text(json.dumps(observed,indent=2)+'\n')
                    break
                time.sleep(.01)
        except Exception as error:result.update(status='FAIL',first_error=repr(error))
        finally:
            if child is not None:result['time_exit']=child.wait()
    remaining=[]
    for pid,row in seen.items():
        try:
            now=proc(pid)
            if now['start_ticks']==row['start_ticks']:remaining.append(now)
        except (FileNotFoundError,ProcessLookupError):pass
    result.update(wall_s=time.monotonic()-started,remaining_observed_owned=remaining,observation=observed)
    raw=output/'result.json';original_ok=False
    if raw.exists():
        r=json.loads(raw.read_text());res=r['resources'];h=r.get('raw_Hub_result',{})
        result['runner_small']=dict(status=r['status'],first_error=r.get('first_error'),checks=r['checks'],
            wall_s=r['wall_s'],resources=res,Hub_status=h.get('status'),native_exit=h.get('native_exit'),
            copy_complete=h.get('native_evidence_storage',{}).get('complete'))
        original_ok=(r['status']=='PASS_NATIVE_BYTES_ONLY' and all(r['checks'].values()) and res['hub_exit']==0
            and h.get('status')=='PASS' and h.get('native_exit')==0 and h.get('native_evidence_storage',{}).get('complete') is True
            and not res['forced_signals'] and not res['remaining_owned_native'])
    load_ok=observed is not None and all(observed[k] for k in ('exact13_names','all_in_expected_root',
        'exact_native_executable','native_parent_is_Hub','actual_time_root_in_chain'))
    if cpu_clean:load_ok=load_ok and observed is not None and observed['cpu_clean_exec_verified']
    if pcap_shim:load_ok=load_ok and observed is not None and observed['pcap_shim_exec_verified']
    if result['status']!='FAIL':
        result['status']='PASS_LOADED_NATIVE_BYTE_SCOPE' if original_ok and load_ok and result.get('time_exit')==0 and not remaining else 'FAIL'
    with (folder/'wrapper-result.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(dict(arm=arm,status=result['status'],time_exit=result.get('time_exit'),wall_s=result['wall_s'],evidence=str(folder))))
    return 0 if result['status']=='PASS_LOADED_NATIVE_BYTE_SCOPE' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--arm',choices=('reference','candidate'),required=True)
    raise SystemExit(main(parser.parse_args().arm))
