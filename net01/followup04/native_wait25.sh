#!/bin/sh
set -eu
trace_dir=/dev/shm/net01-native-wait-25
mkdir -m 700 "$trace_dir"
python3 -B -c 'import json,time; a=time.monotonic_ns(); r=time.time_ns(); b=time.monotonic_ns(); print(json.dumps(dict(monotonic_before_ns=a,realtime_ns=r,monotonic_after_ns=b)))' > "$trace_dir/clock-pair-start.json"
exec /usr/bin/strace -f -ttt -T -yy -s0 -e trace=write,writev,pwrite64,fsync,fdatasync,futex,read,pread64,nanosleep,clock_nanosleep,sched_yield -o "$trace_dir/syscalls.log" /home/zhuyulab/ns3-workspace/net-01/build/followup03-release-portable-native/net01-payload "$@"
