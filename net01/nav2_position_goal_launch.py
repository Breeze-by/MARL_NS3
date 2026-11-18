"""Explicit XY task GoalChecker, over unchanged native footprint prevention."""
import importlib.util
import json
from pathlib import Path
from launch import LaunchDescription
from launch.actions import OpaqueFunction
import yaml
HERE=Path(__file__).resolve().parent
REVISION='xy-position-goal-checker-v1'
CONTRACT=HERE/'config/NAVIGATION_POSITION_GOAL_CHECKER_V1.json'
spec=importlib.util.spec_from_file_location('position_goal_footprint_base',HERE/'nav2_footprint_critic_launch.py')
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

def launch_setup(context):
    contract=json.loads(CONTRACT.read_text())
    if (context.environment.get('NET01_NAVIGATION_GOAL_CHECKER_REVISION')!=contract['revision']
            or context.environment.get('NET01_FRONTIER_INTENT_REVISION')):
        raise ValueError('Position checker requires explicit revision with frontier reservations disabled')
    actions=base.launch_setup(context)
    directory=Path(context.environment['BASE01_RUN_DIR'])
    changes=[]
    for robot in ('tb1','tb2','tb3'):
        path=directory/f'peer_nav2_{robot}.yaml';text=path.read_text();parameters=yaml.safe_load(text)
        controller=parameters['controller_server']['ros__parameters'];name=contract['goal_checker_id'];values=controller[name]
        if (controller['goal_checker_plugins']!=[name] or values['plugin']!=contract['original_plugin']
                or values['xy_goal_tolerance']!=contract['xy_goal_tolerance_m']
                or values['stateful'] is not contract['stateful']):
            raise ValueError('Position checker requires original pluginID/XY/stateful')
        previous=dict(values);values['plugin']=contract['selected_plugin']
        saved=directory/f'peer_nav2_{robot}.before-position-goal-checker.yaml'
        with saved.open('x') as stream:stream.write(text)
        path.write_text(yaml.safe_dump(parameters,sort_keys=False))
        changes.append(dict(robot=robot,effective_params=str(path),original_params=str(saved),previous=previous,current=dict(values)))
    with (directory/'navigation-goal-checker-revision.json').open('x') as stream:
        json.dump(dict(revision=REVISION,contract=contract,launch_entry=str(Path(__file__).resolve()),predecessor_launch=str(HERE/'nav2_footprint_critic_launch.py'),applied_before_actions=True,changes=changes),stream,indent=2)
        stream.write('\n')
    return actions

def generate_launch_description():
    return LaunchDescription([OpaqueFunction(function=launch_setup) if isinstance(action,OpaqueFunction) else action for action in base.generate_launch_description().entities])
