"""Thin, separately admitted old/new native runner observation. No transport changes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

REPO=Path(__file__).resolve().parents[3]
WORKSPACE=REPO.parents[1]
CANDIDATE=WORKSPACE/'net-01d/ns3-lto-portable-followup02'
BASE=REPO/'net01d/followup02'
MODULES={'wifi','internet','csma','mobility','propagation','spectrum','antenna',
         'energy','network','core','traffic-control','bridge','stats'}


def proc(pid):
    root=Path('/proc')/str(pid)
    stat=root.joinpath('stat').read_text().rsplit(') ',1)[1].split()
    return dict(pid=pid,ppid=int(stat[1]),pgid=int(stat[2]),state=stat[0],start_ticks=int(stat[19]),
                argv=[os.fsdecode(s) for s in root.joinpath('cmdline').read_bytes().rstrip(b'\0').split(b'\0')])


def owned_tree(root_pid):
    """Walk only descendants of this actual time launcher, including thread children."""
    todo=[root_pid];rows={}
    while todo:
        pid=todo.pop()
        if pid in rows:continue
        try:
            row=proc(pid);rows[pid]=row
            for task in (Path('/proc')/str(pid)/'task').iterdir():
                try:children=task.joinpath('children').read_text().split()
                except FileNotFoundError:continue
                for value in children:
                    child=int(value)
                    try:
                        if proc(child)['ppid']==pid:todo.append(child)
                    except (FileNotFoundError,ProcessLookupError):pass
        except (FileNotFoundError,ProcessLookupError):pass
    return rows


def main(arm):
    reference=arm=='reference'
    name='ntcp-lto-r1' if reference else 'ntcp-lto-c1'
    binary=(WORKSPACE/'net-01d/build/followup02-native-tcp-mtu-v2/net01-payload-tcp'
            if reference else CANDIDATE/'driver-out/net01-payload-tcp')
    libraries=(WORKSPACE/'net-01/ns3-release-portable-followup03/build/lib'
               if reference else CANDIDATE/'build/lib')
    folder=BASE/'native/lto-pair-01'/arm;folder.mkdir(parents=True,exist_ok=False)
    output=BASE/'runs'/name;ram=Path('/dev/shm')/('net01d-f02-'+name)
    time_file=CANDIDATE/'evidence'/('reference-total-time.txt' if reference else 'candidate-total-time.txt')
    command=['/usr/bin/time','-v','-o',str(time_file),'timeout','--signal=TERM','--kill-after=2s','30s',
        'python3','-B','net01d/followup02/native/run_native_tcp.py','--case','stream-01',
        '--output-name',name,'--native-transport','tcp-mtu-v2','--native',str(binary)]
    env=os.environ.copy()
    for key in ('LD_PRELOAD','LD_AUDIT'):env.pop(key,None)
    env['LD_LIBRARY_PATH']=str(libraries)
    result=dict(arm=arm,status='NOT_STARTED',argv=command,cwd=str(REPO),native=str(binary),
        environment=dict(LD_LIBRARY_PATH=str(libraries),LD_PRELOAD='UNSET',LD_AUDIT='UNSET'),
        output=str(output),RAM=str(ram),time_v_file=str(time_file),
        time_scope='Runner+waited child subtree CPU/wall, includesHub/copy/summary; notpureNative. Observerparent CPU excluded.',
        observation_scope='10ms owned-tree discovery untilone nativeREADY/maps capture; no runtime sampling thereafter')
    process=None;seen={};observation=None;started=time.monotonic()
    stdout=stderr=None
    try:
        if not reference:
            prior=json.loads((BASE/'native/lto-pair-01/reference/wrapper-result.json').read_text())
            if prior['status']!='PASS_LOADED_NATIVE_BYTE_SCOPE':
                raise RuntimeError('Reference arm did notpass; candidate notstarted')
        for path in (binary,libraries,Path('/usr/bin/time')):
            if not path.exists():raise FileNotFoundError(path)
        if output.exists() or ram.exists() or time_file.exists():
            raise FileExistsError('Exclusive run/RAM/time output alreadyexists')
        if len(os.fsencode(output/'wire.sock'))>=108:raise ValueError('HostUnix socketpath too long')
        (folder/'argv.json').write_text(json.dumps(command,indent=2)+'\n')
        (folder/'environment.json').write_text(json.dumps(result['environment'],indent=2)+'\n')
        stdout=(folder/'stdout.log').open('x');stderr=(folder/'stderr.log').open('x')
        process=subprocess.Popen(command,cwd=REPO,env=env,stdout=stdout,stderr=stderr)
        result.update(status='RUNNING',time_pid=process.pid)
        (folder/'owner.json').write_text(json.dumps(proc(process.pid),indent=2)+'\n')
        while process.poll() is None:
            tree=owned_tree(process.pid);seen.update(tree)
            matches=[r for r in tree.values() if r['argv'] and r['argv'][0]==str(binary)]
            if len(matches)>1:raise RuntimeError('Multiple matchingowned nativechildren')
            # Hub creates its socket only after actual nativeREADY, so loader
            # startup cannot be misclassified as missinglibraries.
            if matches and (output/'wire.sock').exists():
                row=matches[0];begin=time.monotonic_ns();maps=Path('/proc',str(row['pid']),'maps').read_text()
                executable=os.readlink(Path('/proc',str(row['pid']),'exe'))
                (folder/'native.maps.txt').write_text(maps)
                mapped={line.split(None,5)[5] for line in maps.splitlines()
                        if len(line.split(None,5))==6 and Path(line.split(None,5)[5]).name.startswith('libns3.40-')}
                expected={'libns3.40-'+module+'.so' for module in MODULES}
                names={Path(path).name for path in mapped}
                belonging=all(Path(path).resolve().parent==libraries.resolve() for path in mapped)
                chain=[];cursor=row['pid']
                while cursor in tree:
                    chain.append(tree[cursor]);cursor=tree[cursor]['ppid']
                runner_seen=any('net01d/followup02/native/run_native_tcp.py' in r['argv'] for r in chain)
                hub_seen=any(str(REPO/'net01/tools/packet_hub.py') in r['argv'] for r in chain)
                observation=dict(native=row,ancestry_native_to_time=chain,exe=executable,
                    begin_monotonic_ns=begin,end_monotonic_ns=time.monotonic_ns(),
                    mapped_ns3_paths=sorted(mapped),expected_names=sorted(expected),
                    actual13_names=names==expected,all_in_expected_root=bool(mapped) and belonging,
                    exact_native_executable=Path(executable).resolve()==binary.resolve(),
                    runner_and_Hub_in_owned_chain=runner_seen and hub_seen,
                    actual_time_root_in_chain=process.pid in {r['pid'] for r in chain})
                result['observation']=observation
                (folder/'native-observation.json').write_text(json.dumps(observation,indent=2)+'\n')
                break  # Observation ends now; the original runner owns all bounds/cleanup.
            time.sleep(.01)  # Observer discovery only, no business/simulation timing role.
    except Exception as error:
        result.update(status='FAIL',first_error=repr(error))
    finally:
        if process is not None:result['time_exit']=process.wait()
        if stdout is not None:stdout.close();stderr.close()
        remaining=[]
        for pid,row in seen.items():
            try:
                current=proc(pid)
                if current['start_ticks']==row['start_ticks']:remaining.append(current)
            except (FileNotFoundError,ProcessLookupError):pass
        result.update(wall_s=time.monotonic()-started,remaining_observed_owned=remaining)
        raw=output/'result.json'
        result['original_byte_resource_pass']=False
        if raw.exists():
            try:
                runner=json.loads(raw.read_text());resources=runner['resources'];hub=runner.get('raw_Hub_result',{})
                result['runner_small']=dict(status=runner['status'],first_error=runner.get('first_error'),
                    wall_s=runner['wall_s'],resources=resources,native_exit=hub.get('native_exit'),Hub_status=hub.get('status'),
                    copy_complete=hub.get('native_evidence_storage',{}).get('complete'))
                result['original_byte_resource_pass']=(runner['status']=='PASS_NATIVE_BYTES_ONLY'
                    and resources['hub_exit']==0 and hub.get('status')=='PASS' and hub.get('native_exit')==0
                    and hub.get('native_evidence_storage',{}).get('complete') is True
                    and not resources['forced_signals'] and not resources['remaining_owned_native'])
            except (ValueError,KeyError) as error:
                result.update(status='FAIL',runner_evidence_error=repr(error))
                result.setdefault('first_error','Originalrunner evidence incomplete afterexit')
        if result['status']!='FAIL':
            if observation is None:result.update(status='NOT_OBSERVED',first_error='Actualnative maps notobserved')
            elif not all(observation[k] for k in ('actual13_names','all_in_expected_root',
                    'exact_native_executable','runner_and_Hub_in_owned_chain','actual_time_root_in_chain')):
                result.update(status='FAIL',first_error='ActualELF/13DSO/ownedchain proof failed')
            elif result.get('time_exit')!=0 or not time_file.is_file() or not result['original_byte_resource_pass'] or remaining:
                result.update(status='FAIL',first_error='Originalrunner/time/resource evidence failed')
            else:result['status']='PASS_LOADED_NATIVE_BYTE_SCOPE'
        (folder/'wrapper-result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(arm=arm,status=result['status'],first_error=result.get('first_error'),
            time_exit=result.get('time_exit'),wall_s=result['wall_s'],evidence=str(folder))),flush=True)
    return 0 if result['status']=='PASS_LOADED_NATIVE_BYTE_SCOPE' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--arm',choices=('reference','candidate'),required=True)
    raise SystemExit(main(parser.parse_args().arm))
