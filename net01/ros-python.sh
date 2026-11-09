#!/usr/bin/env bash
set -euo pipefail
net_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
host_workspace=$(cd -- "$net_repo/../.." && pwd)
baseline_dir="$host_workspace/base-01-econ"
mkdir -p "$net_repo/runtime-home"
exec bwrap --unshare-user --uid 0 --gid 0 --die-with-parent \
  --ro-bind "$baseline_dir/isolation/rootfs" / --tmpfs /tmp \
  --bind "$net_repo/runtime-home" /root \
  --ro-bind /proc /proc --dev-bind /dev /dev --ro-bind /sys /sys \
  --ro-bind "$baseline_dir" /project --bind "$net_repo" /mnt --chdir /mnt \
  --ro-bind /home/zhuyulab/.local/lib/python3.10/site-packages /tmp/rl02-python \
  /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LANG=C.UTF-8 \
  ROS_DOMAIN_ID=92 ROS_LOCALHOST_ONLY=1 RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /bin/bash --noprofile --norc -c '
    source /opt/ros/humble/setup.bash
    source /project/workspace/install/setup.bash
    export PYTHONPATH=/mnt/net01:/mnt/workspace/gz01:/mnt/workspace/rl04:/mnt/workspace/rl02:/mnt/workspace/rl01:/mnt/workspace/src/multi_robot_exploration:/tmp/rl02-python:${PYTHONPATH:-}
    exec python3 -B "$@"
  ' bash "$@"
