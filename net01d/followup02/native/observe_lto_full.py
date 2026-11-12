"""One opt-in outer launch observation; the unchanged replay owns all control/cleanup."""
import json
import os
from pathlib import Path
import subprocess
import time
from observe_lto_pair import proc, owned_tree, MODULES, REPO, BASE


def main(admission_path=None,folder=None):
    admission=json.loads((BASE/'TCP_LTO_FULL_ADMISSION.json' if admission_path is None else admission_path).read_text())
    if admission['execution_authorized'] is not True:raise RuntimeError('Root full admission is pending')
    output=Path(admission['output']);native=Path(admission['argv'][admission['argv'].index('--native')+1])
    libraries=Path(admission['environment']['LD_LIBRARY_PATH'])
    folder=BASE/'evidence/tcp-lto-01-loader' if folder is None else folder
    folder.mkdir(exist_ok=False)
    if output.exists() or Path(admission['RAM']).exists():raise FileExistsError('Exclusive case/RAM exists')
    env=os.environ.copy()
    for name in ('LD_PRELOAD','LD_AUDIT'):env.pop(name,None)
    env['LD_LIBRARY_PATH']=str(libraries)
    (folder/'argv.json').write_text(json.dumps(admission['argv'],indent=2)+'\n')
    (folder/'environment.json').write_text(json.dumps(admission['environment'],indent=2)+'\n')
    result=dict(status='NOT_OBSERVED',source=admission['source_checkpoint'],
        scope='Original full-harness exit and one actual load proof only; not fullqualification',
        native_sha256_reused=admission['native_sha256_reused'],environment=admission['environment'])
    child=None;observed=None;known={};begin=time.monotonic()
    stdout=(folder/'stdout.log').open('x');stderr=(folder/'stderr.log').open('x')
    try:
        child=subprocess.Popen(admission['argv'],cwd=admission['cwd'],env=env,stdout=stdout,stderr=stderr)
        result['launcher_pid']=child.pid
        (folder/'owner.json').write_text(json.dumps(proc(child.pid),indent=2)+'\n')
        while child.poll() is None:
            try:owners=json.loads((output/'owned-processes.json').read_text())
            except (FileNotFoundError,json.JSONDecodeError):
                time.sleep(.01);continue  # The original harness rewrites this small in-flight file.
            if not owners.get('hub') or not owners.get('native_children') or not (output/'wire.sock').exists():
                time.sleep(.01);continue
            hub=proc(owners['hub']['pid']);known[hub['pid']]=hub
            expected_hub=str(REPO/'net01/tools/packet_hub.py')
            if expected_hub not in hub['argv'] or str(native) not in hub['argv'] or str(output/'hub') not in hub['argv']:
                raise RuntimeError('Recorded Hub actual argv does not match this case')
            chain=[];cursor=hub['pid']
            while cursor>1:
                row=proc(cursor);chain.append(row)
                if cursor==child.pid:break
                cursor=row['ppid']
            if not chain or chain[-1]['pid']!=child.pid:raise RuntimeError('Hub outside actual launched tree')
            tree=owned_tree(hub['pid']);known.update(tree)
            ids={int(pid) for pid in owners['native_children']}
            matches=[r for pid,r in tree.items() if pid in ids and r['argv'] and r['argv'][0]==str(native)]
            if len(matches)!=1:raise RuntimeError('Actual owned native identity missing/ambiguous')
            row=matches[0];start=time.monotonic_ns()
            maps=Path('/proc',str(row['pid']),'maps').read_text()
            exe=os.readlink(Path('/proc',str(row['pid']),'exe'))
            (folder/'native.maps.txt').write_text(maps)
            mapped={line.split(None,5)[5] for line in maps.splitlines()
                if len(line.split(None,5))==6 and Path(line.split(None,5)[5]).name.startswith('libns3.40-')}
            expected={'libns3.40-'+module+'.so' for module in MODULES}
            observed=dict(native=row,Hub_to_launcher_ancestry=chain,exe=exe,
                begin_monotonic_ns=start,end_monotonic_ns=time.monotonic_ns(),mapped_ns3_paths=sorted(mapped),
                exact13_names={Path(p).name for p in mapped}==expected,
                all_in_expected_root=bool(mapped) and all(Path(p).resolve().parent==libraries.resolve() for p in mapped),
                actual_exe_matches=Path(exe).resolve()==native.resolve(),
                actual_native_parent_is_Hub=row['ppid']==hub['pid'])
            (folder/'native-observation.json').write_text(json.dumps(observed,indent=2)+'\n')
            break  # No continued observation, ROS interaction or control message.
    except Exception as error:
        result['observer_error']=repr(error)
    finally:
        if child is not None:result['harness_exit']=child.wait()  # Original32/60 bounds and cleanup only.
        stdout.close();stderr.close()
        remaining=[]
        for pid,old in known.items():
            try:
                now=proc(pid)
                if now['start_ticks']==old['start_ticks']:remaining.append(now)
            except (FileNotFoundError,ProcessLookupError):pass
        result.update(wall_s=time.monotonic()-begin,observation=observed,remaining_observed_owned=remaining)
        original=output/'process-exit.json'
        if original.exists():
            try:result['original_process_exit']=json.loads(original.read_text())
            except (ValueError,OSError) as error:result['process_exit_evidence_error']=repr(error)
        load_ok=observed is not None and all(observed[key] for key in
            ('exact13_names','all_in_expected_root','actual_exe_matches','actual_native_parent_is_Hub'))
        result['status']=('PROCESS_EXIT0_LOAD_PROOF_ONLY' if load_ok and result.get('harness_exit')==0
            and not remaining and not result.get('observer_error') and 'original_process_exit' in result
            else 'FAIL_OR_LOAD_NOT_OBSERVED')
        (folder/'outer-result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(status=result['status'],harness_exit=result.get('harness_exit'),
            observer_error=result.get('observer_error'),wall_s=result['wall_s'],evidence=str(folder))),flush=True)
    return 0 if result['status']=='PROCESS_EXIT0_LOAD_PROOF_ONLY' else 1


if __name__=='__main__':raise SystemExit(main())
