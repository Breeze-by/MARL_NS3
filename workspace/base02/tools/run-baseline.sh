#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source /project/workspace/install/setup.bash
export PYTHONPATH=/mnt/workspace/src/multi_robot_exploration:${PYTHONPATH:-}
export TURTLEBOT3_MODEL=waffle
export GAZEBO_MASTER_URI=http://127.0.0.1:11662
export GAZEBO_MODEL_DATABASE_URI=''
export GAZEBO_MODEL_PATH=/project/assets/gazebo_models:${GAZEBO_MODEL_PATH:-}
export DISPLAY=:62
if [[ -e "$1" || -e "$1.xvfb.log" ]]; then
  echo "Refusing to overwrite existing case: $1" >&2
  exit 1
fi
Xvfb "$DISPLAY" -screen 0 1280x800x24 -nolisten tcp > "$1.xvfb.log" 2>&1 &
xvfb_pid=$!
trap 'kill "$xvfb_pid" 2>/dev/null || true; wait "$xvfb_pid" 2>/dev/null || true' EXIT
python3 /mnt/tools/run_baseline.py "$@"
