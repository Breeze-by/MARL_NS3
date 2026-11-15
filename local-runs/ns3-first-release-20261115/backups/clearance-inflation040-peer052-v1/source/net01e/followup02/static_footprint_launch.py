"""Candidate common execution revision; does not authorize a Gazebo run.

Call the existing NET/frozen launch setup, change only this case's generated
global static-layer parameter before returning its original launch actions.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys

from launch import LaunchDescription
from launch.actions import OpaqueFunction
import yaml

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'net01'))
BASE_PATH=REPO/'net01/net_scene_launch.py'
spec=importlib.util.spec_from_file_location('static_footprint_original_net_launch',BASE_PATH)
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
REVISION='static-footprint-common-v1'


def launch_setup(context):
    actions=base.launch_setup(context)
    directory=Path(context.environment['BASE01_RUN_DIR'])
    changes=[]
    for robot in ('tb1','tb2','tb3'):
        path=directory/f'peer_nav2_{robot}.yaml'
        text=path.read_text();before=yaml.safe_load(text);after=copy.deepcopy(before)
        static=after['global_costmap']['global_costmap']['ros__parameters']['static_layer']
        old=static.get('footprint_clearing_enabled',False)
        if old is not False:raise RuntimeError('Candidate requires original static clearing disabled')
        static['footprint_clearing_enabled']=True
        saved=directory/f'peer_nav2_{robot}.before-static-footprint.yaml'
        with saved.open('x') as stream:stream.write(text)
        path.write_text(yaml.safe_dump(after,sort_keys=False))
        changes.append(dict(robot=robot,effective_params=str(path),original_params=str(saved),
            parameter='global_costmap.global_costmap.ros__parameters.static_layer.footprint_clearing_enabled',
            previous_declared='footprint_clearing_enabled' in before['global_costmap']['global_costmap']['ros__parameters']['static_layer'],
            previous_value=old,value=True))
    with (directory/'common-execution-revision.json').open('x') as stream:
        json.dump(dict(revision=REVISION,launch_entry=str(Path(__file__).resolve()),
            predecessor_launch=str(BASE_PATH),applied_before_actions=True,changes=changes,
            scope='common execution config; frozen behavior and raw SLAM/shared maps unchanged'),stream,indent=2)
        stream.write('\n')
    return actions


def generate_launch_description():
    entities=list(base.generate_launch_description().entities)
    if sum(isinstance(action,OpaqueFunction) for action in entities)!=1:
        raise RuntimeError('Expected one existing NET launch setup')
    return LaunchDescription([OpaqueFunction(function=launch_setup) if isinstance(action,OpaqueFunction)
                              else action for action in entities])
