"""One rootfs-only recorder/parser and direct launch-reference check.

Imports installed ROS CLI classes, but never calls recorder.main, rclpy.init,
Node, launch, Gazebo, model inference or any transport/Action fixture.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import run_network_case as adapter
from ament_index_python.packages import get_package_share_directory,get_package_prefix
from ros2bag.verb.record import RecordVerb
import yaml


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    old=HERE.parent/"runs/net01-a-corridor-6201-01/events.jsonl"
    original=next(json.loads(line)["argv"] for line in old.read_text().splitlines()
        if json.loads(line)["kind"]=="bag_command")
    adapter.subprocess=SimpleNamespace(Popen=lambda command,*a,**kw:command)
    command=adapter.popen(original)
    cli=argparse.ArgumentParser()
    RecordVerb().add_arguments(cli,"ros2 bag")
    parsed=cli.parse_args(command[3:])
    qos_path=Path(parsed.qos_profile_overrides_path.name)
    qos=yaml.safe_load(parsed.qos_profile_overrides_path)
    parsed.qos_profile_overrides_path.close()
    multi=Path(get_package_share_directory("multi_robot"))
    scene=HERE.parent/"inputs/scenes/regression-corridor-common-6201-dwb-v1.json"
    world=HERE.parent/json.loads(scene.read_text())["world_relative_phase"]
    paths=[qos_path,scene,world,HERE/"net_scene_launch.py",HERE/"gateway.py",HERE/"bound_peer.py",
        HERE.parent/"workspace/gz01/headquarters.py",
        HERE.parent/"workspace/src/merge_map/merge_map/merge_map.py",
        *[HERE.parent/"runs"/p for p in ["selection.json","formal-01/checkpoint-00512.pt","formal-01/summary.json","formal-01/process-exit.json"]],
        Path(get_package_share_directory("gazebo_ros"))/"launch/gzserver.launch.py",
        multi/"launch/nav2_bringup/bringup_launch.py",multi/"urdf/turtlebot3_waffle.urdf",
        multi/"models/turtlebot3_waffle/model.sdf",multi/"../../../../src/multi_robot/maps/turtlebot3_world.yaml",
        *[multi/f"params/nav2_params_tb{r}_0.yaml" for r in (1,2,3)],
        Path(get_package_share_directory("slam_toolbox"))/"config/mapper_params_online_multi_async.yaml",
        Path(get_package_share_directory("nav2_bt_navigator"))/"behavior_trees/navigate_to_pose_w_replanning_and_recovery.xml"]
    references=[dict(path=str(p),resolved=str(p.resolve()),readable=p.is_file() and os.access(p,os.R_OK)) for p in paths]
    executable_pairs=[("gazebo_ros","spawn_entity.py"),("robot_state_publisher","robot_state_publisher"),
        ("joint_state_publisher","joint_state_publisher"),("slam_toolbox","multirobot_slam_toolbox_node"),
        ("tf2_ros","static_transform_publisher")]
    executables=[]
    for package,name in executable_pairs:
        p=Path(get_package_prefix(package))/"lib"/package/name
        executables.append(dict(path=str(p),executable=p.is_file() and os.access(p,os.X_OK)))
    for name in ["ros2","python3","gzserver","Xvfb"]:
        p=shutil.which(name);executables.append(dict(path=p,executable=p is not None))
    checks=dict(installed_recorder_parser_accepts_original_flags=True,
        actual_external_qos_path_readable=qos_path==HERE/"config/recorder-qos.yaml" and os.access(qos_path,os.R_OK),
        original_tf_static_depth100=all(qos[f"/tb{r}/tf_static"]["depth"]==100 for r in (1,2,3)),
        original_map_TL=all(qos[t]["durability"]=="transient_local" for t in ["/merge_map","/tb1/map","/tb2/map","/tb3/map"]),
        direct_launch_refs_readable=all(p["readable"] for p in references),
        installed_executables_present=all(p["executable"] for p in executables))
    result=dict(status="PASS" if all(checks.values()) else "FAIL",checks=checks,
        recorder_argv=command,recorder_topics=parsed.topics,references=references,executables=executables,
        scope="Actual ros-python.sh/rootfs installed CLI parsing and direct file references only; recorder.main/rclpy.init/Node/GZ/NN not invoked",
        Gazebo_starts=0,ROS_Node=0,NN=0)
    with args.output.open("x") as stream:json.dump(result,stream,indent=2)
    print(json.dumps(dict(status=result["status"],checks=checks,output=str(args.output))),flush=True)
    return 0 if all(checks.values()) else 1


if __name__=="__main__":raise SystemExit(main())
