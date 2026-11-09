from pathlib import Path
import ast
import json
import subprocess
import sys

base=Path('/home/zhuyulab/ns3-workspace/net-01/workspace/net01/followup04')
evidence=base/'evidence/native-wait-wrapper-static-01'
wrapper=base/'native_wait_wrapper.py'
ast.parse(wrapper.read_text(),filename=str(wrapper))
diag=Path('/dev/shm/net01-native-wait-wrapper-check-01')
child="import os,sys,time; assert sys.argv[1:]==['space arg','--literal']; payload=sys.stdin.buffer.read(); os.write(1,b'out:'+payload); os.write(2,b'child-stderr\\n'); time.sleep(.10); sys.exit(7)"
command=[sys.executable,'-B',str(wrapper),sys.executable,str(diag),'-B','-c',child,'space arg','--literal']
(evidence/'command.json').write_text(json.dumps(command,indent=2)+'\n')
payload=b'one\x00two\n'
process=subprocess.run(command,input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
(evidence/'stdout.bin').write_bytes(process.stdout)
(evidence/'stderr.bin').write_bytes(process.stderr)
(evidence/'process-exit.json').write_text(json.dumps(dict(actual_wrapper_exit=process.returncode))+'\n')
trace=(diag/'trace.jsonl').read_bytes()
(evidence/'trace.jsonl').write_bytes(trace)
rows=[json.loads(line) for line in trace.splitlines()]
start=rows[0];end=rows[-1];samples=[r for r in rows if r['kind']=='sample']
checks=dict(ast_parses=True,actual_exit7=process.returncode==7,
    binary_stdin_stdout_exact=process.stdout==b'out:'+payload,
    stderr_exact=process.stderr==b'child-stderr\\n',
    argv_exact=start['actual_child_argv']==command[4:],
    start_and_end=rows[0]['kind']=='wrapper_start' and rows[-1]['kind']=='wrapper_end',
    samples_present=len(samples)>=2,
    stat_and_schedstat_fields=all(all(k in r for k in ('state','utime_ticks','stime_ticks','minfault','majfault','nice','policy','running_ns','runqueue_ns','timeslices')) for r in samples),
    clocks_and_proc_read_span=all(all(k in r for k in ('monotonic_ns','realtime_ns','sample_begin_monotonic_ns','proc_read_wall_ns','wchan','syscall')) for r in samples),
    single_direct_child_pid=len({r['child_pid'] for r in rows if 'child_pid' in r})==1,
    rusage_and_exit=end['actual_child_exit']==7 and end['child_rusage'] is not None,
    no_wrapper_error=not any(r['kind']=='wrapper_error' for r in rows))
# The child's executable precedes DIAGNOSTIC_DIR in wrapper argv; its
# arguments resume immediately after that directory.
checks['argv_exact']=start['actual_child_argv']==[command[4],*command[6:]]
result=dict(scope='0 ROS init / 0 Node / 0 ns3 / 0 GZ; one controlled stdlib child',
    checks=checks,pass_=all(checks.values()),samples=len(samples),
    syscall_permission_errors=sum(isinstance(r['syscall'],dict) for r in samples),
    actual_wrapper_exit=process.returncode,wrapper_end=end,
    actual_ram_trace=str(diag/'trace.jsonl'))
(evidence/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['pass_'] else 1)
