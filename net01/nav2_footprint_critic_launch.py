"""Explicit native padded-footprint DWB collision critic over reviewed q Nav2."""
import importlib.util
import json
from pathlib import Path
from launch import LaunchDescription
from launch.actions import OpaqueFunction
import yaml
from shared_navigation_map import selected as shared_navigation_selected, apply_static_topic, topic

HERE = Path(__file__).resolve().parent
REVISION = 'dwb-padded-footprint-obstacle-prevention-v1'
CONTRACT = HERE/'config/NAVIGATION_DWB_FOOTPRINT_PREVENTION_V1.json'
spec = importlib.util.spec_from_file_location('footprint_critic_smac_base', HERE/'nav2_smac_launch.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def launch_setup(context):
    contract = json.loads(CONTRACT.read_text())
    if context.environment.get('NET01_NAVIGATION_CONTROLLER_REVISION') != contract['revision']:
        raise ValueError('Footprint critic launch requires explicit controller revision')
    actions = base.launch_setup(context)
    directory = Path(context.environment['BASE01_RUN_DIR'])
    changes = []
    shared_navigation = shared_navigation_selected(context.environment)
    for robot in ('tb1', 'tb2', 'tb3'):
        path = directory/f'peer_nav2_{robot}.yaml'
        text = path.read_text()
        parameters = yaml.safe_load(text)
        controller = parameters['controller_server']['ros__parameters']
        values = controller[contract['controller_id']]
        local = parameters['local_costmap']['local_costmap']['ros__parameters']
        if (controller['controller_plugins'] != [contract['controller_id']]
                or values['plugin'] != contract['controller_plugin']
                or values['critics'] != contract['original_critics']
                or values['BaseObstacle.scale'] != contract['original_configured_scale']
                or local['resolution'] != contract['costmap_resolution_m']
                or local['robot_radius'] != contract['robot_radius_m']):
            raise ValueError('Footprint critic requires unchanged reviewed DWB/footprint/weight')
        previous = dict(critics=list(values['critics']), scale=values['BaseObstacle.scale'])
        values['critics'] = [contract['selected_critic'] if name == contract['original_critic'] else name
                             for name in values['critics']]
        values.pop('BaseObstacle.scale')
        values['ObstacleFootprint.scale'] = contract['selected_configured_scale']
        if shared_navigation:
            apply_static_topic(parameters, robot)
        saved = directory/f'peer_nav2_{robot}.before-footprint-critic.yaml'
        with saved.open('x') as stream:
            stream.write(text)
        path.write_text(yaml.safe_dump(parameters, sort_keys=False))
        changes.append(dict(robot=robot, effective_params=str(path), original_params=str(saved),
                            previous=previous, current=dict(critics=values['critics'],
                            configured_scale=values['ObstacleFootprint.scale'],
                            resolution_m=local['resolution'],
                            effective_native_scale=local['resolution']*values['ObstacleFootprint.scale']),
                            robot_radius_m=local['robot_radius'],
                            footprint_padding_explicit=local.get('footprint_padding'),
                            **(dict(shared_navigation_map=dict(revision=shared_navigation,
                                global_static_topic=topic(robot), previous_topic=f'/{robot}/map'))
                                if shared_navigation else {})))
    with (directory/'navigation-controller-revision.json').open('x') as stream:
        json.dump(dict(revision=REVISION, launch_entry=str(Path(__file__).resolve()),
                       predecessor_launch=str(HERE/'nav2_smac_launch.py'), contract=contract,
                       applied_before_actions=True, changes=changes), stream, indent=2)
        stream.write('\n')
    return actions


def generate_launch_description():
    entities = list(base.generate_launch_description().entities)
    return LaunchDescription([OpaqueFunction(function=launch_setup) if isinstance(action, OpaqueFunction)
                              else action for action in entities])
