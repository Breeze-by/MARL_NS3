"""Explicit Nav2 sim-clock revision over the existing static-footprint launch.

Only generated node parameters change. Frozen sources and every navigation,
footprint, cost, progress and recovery setting retain their original values.
"""
import importlib.util
import json
from pathlib import Path

from launch import LaunchDescription
from launch.actions import OpaqueFunction
import yaml

REPO=Path(__file__).resolve().parent.parent
PREDECESSOR=REPO/'net01e/followup02/static_footprint_launch.py'
spec=importlib.util.spec_from_file_location('nav2_simclock_static_predecessor',PREDECESSOR)
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
REVISION='nav2-simclock-common-v1'
NAV2_NODES=('controller_server','smoother_server','planner_server','behavior_server',
    'bt_navigator','waypoint_follower','velocity_smoother')


def set_node_sim_clocks(parameters):
    """Use actual launched names; obsolete recoveries_server is not a match."""
    changes=[]
    for node in NAV2_NODES:
        values=parameters.setdefault(node,{}).setdefault('ros__parameters',{})
        previous=values.get('use_sim_time')
        values['use_sim_time']=True
        if previous is not True:
            changes.append(dict(node=node,parameter='use_sim_time',previous=previous,value=True))
    return changes


def launch_setup(context):
    actions=base.launch_setup(context)
    directory=Path(context.environment['BASE01_RUN_DIR'])
    changes=[]
    for robot in ('tb1','tb2','tb3'):
        path=directory/f'peer_nav2_{robot}.yaml'
        text=path.read_text();parameters=yaml.safe_load(text)
        corrected=set_node_sim_clocks(parameters)
        saved=directory/f'peer_nav2_{robot}.before-nav2-simclock.yaml'
        with saved.open('x') as stream:stream.write(text)
        path.write_text(yaml.safe_dump(parameters,sort_keys=False))
        changes.append(dict(robot=robot,effective_params=str(path),original_params=str(saved),changes=corrected))
    previous=directory/'common-execution-revision.json'
    previous.rename(directory/'common-execution-before-nav2-simclock.json')
    with previous.open('x') as stream:
        json.dump(dict(revision=REVISION,launch_entry=str(Path(__file__).resolve()),
            predecessor_launch=str(PREDECESSOR),applied_before_actions=True,changes=changes,
            scope='Only actual enabled Nav2 node use_sim_time keys; policy/701/navigation/safety parameters unchanged'),stream,indent=2)
        stream.write('\n')
    return actions


def generate_launch_description():
    entities=list(base.generate_launch_description().entities)
    return LaunchDescription([OpaqueFunction(function=launch_setup) if isinstance(action,OpaqueFunction)
        else action for action in entities])
