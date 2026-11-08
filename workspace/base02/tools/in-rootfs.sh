#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
baseline_dir=$(cd -- "$project_dir/../base-01-econ" && pwd)
mount_args=(--bind "$project_dir" /project --chdir /project --ro-bind "$baseline_dir/assets" /project/assets)
if [[ ${1:-} == --baseline-runtime ]]; then
  shift
  mount_args=(--ro-bind "$baseline_dir" /project --bind "$project_dir" /mnt --chdir /mnt)
fi
exec bwrap --unshare-user --uid 0 --gid 0 --die-with-parent \
  --ro-bind "$baseline_dir/isolation/rootfs" / --tmpfs /tmp \
  --bind "$project_dir/runtime-home" /root \
  --ro-bind /proc /proc --dev-bind /dev /dev --ro-bind /sys /sys \
  --ro-bind /etc/resolv.conf /etc/resolv.conf \
  "${mount_args[@]}" \
  /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LANG=C.UTF-8 \
  ROS_DOMAIN_ID=62 ROS_LOCALHOST_ONLY=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
  QT_QPA_PLATFORM=offscreen LIBGL_ALWAYS_SOFTWARE=1 \
  /bin/bash --noprofile --norc "$@"
