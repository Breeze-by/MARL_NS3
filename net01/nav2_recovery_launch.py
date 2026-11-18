"""Explicit context-BackUp BT only; original simclock/staticfootprint launch preserved."""
import importlib.util
import json
from pathlib import Path
from launch import LaunchDescription
from launch.actions import OpaqueFunction
import yaml

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('context_backup_original_simclock', HERE/'nav2_simclock_launch.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
REVISION = 'followpath-context-backup-v2'
CONTRACT = HERE/'config/NAVIGATION_RECOVERY_CONTEXT_BACKUP_V2.json'
XML = HERE/'config/NAVIGATE_TO_POSE_CONTEXT_BACKUP_V2.xml'


def launch_setup(context):
    if context.environment.get('NET01_NAVIGATION_RECOVERY_REVISION') != REVISION:
        raise ValueError('Context BackUp launch requires its explicit revision')
    actions = base.launch_setup(context)
    directory = Path(context.environment['BASE01_RUN_DIR'])
    changes = []
    for robot in ('tb1', 'tb2', 'tb3'):
        path = directory/f'peer_nav2_{robot}.yaml'
        text = path.read_text()
        parameters = yaml.safe_load(text)
        values = parameters['bt_navigator']['ros__parameters']
        previous = values.get('default_nav_to_pose_bt_xml')
        values['default_nav_to_pose_bt_xml'] = str(XML)
        saved = directory/f'peer_nav2_{robot}.before-context-backup.yaml'
        with saved.open('x') as stream:
            stream.write(text)
        path.write_text(yaml.safe_dump(parameters, sort_keys=False))
        changes.append(dict(robot=robot, effective_params=str(path), original_params=str(saved),
                            parameter='bt_navigator.ros__parameters.default_nav_to_pose_bt_xml',
                            previous=previous, value=str(XML)))
    with (directory/'navigation-recovery-revision.json').open('x') as stream:
        json.dump(dict(revision=REVISION, launch_entry=str(Path(__file__).resolve()),
                       predecessor_launch=str(HERE/'nav2_simclock_launch.py'),
                       contract=json.loads(CONTRACT.read_text()), XML=str(XML),
                       applied_before_actions=True, changes=changes), stream, indent=2)
        stream.write('\n')
    return actions


def generate_launch_description():
    entities = list(base.generate_launch_description().entities)
    return LaunchDescription([OpaqueFunction(function=launch_setup) if isinstance(action, OpaqueFunction)
                              else action for action in entities])
