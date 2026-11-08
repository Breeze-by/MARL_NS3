#!/usr/bin/env bash
set -euo pipefail
exec /tmp/gdb-host/lib/ld-linux-x86-64.so.2 --library-path /tmp/gdb-host/lib \
  /tmp/gdb-host/gdb --data-directory=/tmp/gdb-host/share --quiet --batch -nx -nh \
  -x "$(dirname -- "${BASH_SOURCE[0]}")/gzserver_gdb.py" --args "$@"
