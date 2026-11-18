"""Raw peer body filter followed by native inflation; recovery-v2 stays intact."""
import importlib.util
import json
from pathlib import Path
from launch import LaunchDescription
from launch.actions import OpaqueFunction
import yaml
from peer_geometry import REVISION, load_contract

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('peer_geometry_recovery_base', HERE/'nav2_recovery_launch.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def launch_setup(context):
    contract = load_contract(context.environment.get('NET01_NAVIGATION_PEER_GEOMETRY_REVISION'))
    actions = base.launch_setup(context)
    directory = Path(context.environment['BASE01_RUN_DIR'])
    changes = []
    for robot in ('tb1', 'tb2', 'tb3'):
        path = directory/f'peer_nav2_{robot}.yaml'
        text = path.read_text()
        parameters = yaml.safe_load(text)
        for costmap in ('local_costmap', 'global_costmap'):
            values = parameters[costmap][costmap]['ros__parameters']
            if values['filters'] != ['peer_keepout']:
                raise ValueError('Peer body geometry requires original sole keepout filter')
            values['filters'] = ['peer_keepout', 'peer_body_inflation']
            values['peer_body_inflation'] = dict(plugin='nav2_costmap_2d::InflationLayer',
                enabled=True, inflation_radius=contract['postfilter_inflation_radius_m'],
                cost_scaling_factor=contract['cost_scaling_factor'],
                inflate_unknown=False, inflate_around_unknown=False)
            changes.append(dict(robot=robot,costmap=costmap,
                filters=values['filters'],peer_body_inflation=values['peer_body_inflation']))
        saved = directory/f'peer_nav2_{robot}.before-peer-body.yaml'
        with saved.open('x') as stream: stream.write(text)
        path.write_text(yaml.safe_dump(parameters, sort_keys=False))
    with (directory/'navigation-peer-geometry-revision.json').open('x') as stream:
        json.dump(dict(revision=contract['revision'],launch_entry=str(Path(__file__).resolve()),
            predecessor_launch=str(HERE/'nav2_recovery_launch.py'),contract=contract,
            applied_before_actions=True,changes=changes),stream,indent=2)
        stream.write('\n')
    return actions


def generate_launch_description():
    entities = list(base.generate_launch_description().entities)
    return LaunchDescription([OpaqueFunction(function=launch_setup) if isinstance(action, OpaqueFunction)
                              else action for action in entities])
