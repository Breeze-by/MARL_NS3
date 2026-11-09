#!/bin/sh
set -eu
native=/home/zhuyulab/ns3-workspace/net-01/build/followup03-release-portable-native/net01-payload
wrapper=/home/zhuyulab/ns3-workspace/net-01/workspace/net01/followup04/native_wait_wrapper.py
diagnostic_dir=/dev/shm/net01-native-wait-26
exec /usr/bin/python3 -B "$wrapper" "$native" "$diagnostic_dir" "$@"
