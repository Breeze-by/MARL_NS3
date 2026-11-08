#!/usr/bin/env bash
set -euo pipefail
# Emulate ownership changes in the single-UID user namespace. Packages are
# installed only into the project's rootfs, never into the host filesystem.
export FAKEROOTDONTTRYCHOWN=1
exec /usr/bin/eatmydata /usr/bin/fakeroot-sysv \
  /usr/bin/env DEBIAN_FRONTEND=noninteractive \
  /usr/bin/apt-get -o APT::Sandbox::User=root \
  -o Dpkg::Options::=--force-unsafe-io "$@"
