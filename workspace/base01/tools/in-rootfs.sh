#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec bwrap --unshare-user --uid 0 --gid 0 --die-with-parent \
  --bind "$project_dir/isolation/rootfs" / \
  --ro-bind /proc /proc --dev-bind /dev /dev --ro-bind /sys /sys \
  --ro-bind /etc/resolv.conf /etc/resolv.conf \
  --bind "$project_dir" /project --chdir /project \
  /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LANG=C.UTF-8 \
  ROS_DOMAIN_ID=61 ROS_LOCALHOST_ONLY=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
  QT_QPA_PLATFORM=offscreen LIBGL_ALWAYS_SOFTWARE=1 \
  /bin/bash --noprofile --norc "$@"
