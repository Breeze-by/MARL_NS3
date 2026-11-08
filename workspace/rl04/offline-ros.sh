#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
baseline_dir=$(cd -- "$project_dir/../base-01-econ" && pwd)
mkdir -p "$project_dir/runtime-home"
exec bwrap --unshare-user --uid 0 --gid 0 --die-with-parent \
  --ro-bind "$baseline_dir/isolation/rootfs" / --tmpfs /tmp \
  --bind "$project_dir/runtime-home" /root \
  --ro-bind /proc /proc --dev-bind /dev /dev --ro-bind /sys /sys \
  --ro-bind "$baseline_dir" /project --bind "$project_dir" /mnt --chdir /mnt \
  --ro-bind "$project_dir/../rl-03" /tmp/prior \
  /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LANG=C.UTF-8 \
  ROS_DOMAIN_ID=68 ROS_LOCALHOST_ONLY=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /bin/bash --noprofile --norc -c '
    source /opt/ros/humble/setup.bash
    source /project/workspace/install/setup.bash
    export PYTHONPATH=/mnt/workspace/rl04:/mnt/workspace/src/multi_robot_exploration:${PYTHONPATH:-}
    exec python3 -B "$@"
  ' bash "$@"
