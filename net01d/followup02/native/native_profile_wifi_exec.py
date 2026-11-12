#!/usr/bin/python3
"""Set profiling only for the final native exec, never the calling Python/Hub."""
import json
import os
from pathlib import Path
import sys
import time

REPO=Path(__file__).resolve().parents[3]
WORKSPACE=REPO.parents[1]
BINARY=WORKSPACE/'net-01d/ns3-lto-portable-followup02/driver-out/net01-payload-tcp'
LIBRARIES=WORKSPACE/'net-01d/ns3-lto-portable-followup02/build/lib'
FOLDER=REPO/'net01d/followup02/native/wifi-profile-01'
PROFILE=FOLDER/'ld-profile'

native_env=os.environ.copy()
for key in ('LD_PRELOAD','LD_AUDIT','LD_PROFILE','LD_PROFILE_OUTPUT'):native_env.pop(key,None)
native_env.update(LD_LIBRARY_PATH=str(LIBRARIES),LD_PROFILE='libns3.40-wifi.so',LD_PROFILE_OUTPUT=str(PROFILE))
argv=[str(BINARY),*sys.argv[1:],'--cpuProfile=1']
record=dict(phase='prepared_before_native_exec',pid=os.getpid(),monotonic_ns=time.monotonic_ns(),
    actual_exec_target=str(BINARY),original_Hub_native_arguments=sys.argv[1:],native_argv=argv,
    native_environment={key:native_env.get(key) for key in ('LD_LIBRARY_PATH','LD_PROFILE','LD_PROFILE_OUTPUT','LD_PRELOAD','LD_AUDIT')},
    wrapper_source=str(Path(__file__).resolve()),scope='Only this exec receives LD_PROFILE; no parent environment mutation.')
with (FOLDER/'native-exec.json').open('x') as stream:json.dump(record,stream,indent=2);stream.write('\n')
with (FOLDER/'native-exec-source.py').open('xb') as stream:stream.write(Path(__file__).read_bytes())
os.execve(BINARY,argv,native_env)
