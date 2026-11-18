"""Explicit Smac2D global planner; all geometry/recovery/local settings retained."""
import importlib.util
import json
from pathlib import Path
from launch import LaunchDescription
from launch.actions import OpaqueFunction
import yaml

HERE=Path(__file__).resolve().parent
REVISION='smac2d-floor-planner-v4'
CONTRACT=HERE/'config/NAVIGATION_SMAC2D_FLOOR_V4.json'
spec=importlib.util.spec_from_file_location('smac_geometry_base',HERE/'nav2_peer_geometry_launch.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)


def launch_setup(context):
    contract=json.loads(CONTRACT.read_text())
    if context.environment.get('NET01_NAVIGATION_PLANNER_REVISION')!=contract['revision']:
        raise ValueError('Smac launch requires explicit planner revision')
    actions=base.launch_setup(context)
    directory=Path(context.environment['BASE01_RUN_DIR']);changes=[]
    for robot in ('tb1','tb2','tb3'):
        path=directory/f'peer_nav2_{robot}.yaml';text=path.read_text();parameters=yaml.safe_load(text)
        planner=parameters['planner_server']['ros__parameters'];values=planner['GridBased'];previous=dict(values)
        if (planner['planner_plugins']!=['GridBased'] or values['plugin']!='nav2_navfn_planner/NavfnPlanner'
            or values['tolerance']!=contract['tolerance'] or values['allow_unknown']!=contract['allow_unknown']
            or values.get('use_final_approach_orientation',False)!=contract['use_final_approach_orientation']):
            raise ValueError('Smac revision requires original reviewed NavFn parameters')
        values['plugin']=contract['plugin'];values.pop('use_astar')
        for key in ('use_final_approach_orientation','downsample_costmap','downsampling_factor','smoother'):
            values[key]=contract[key]
        saved=directory/f'peer_nav2_{robot}.before-smac.yaml'
        with saved.open('x') as stream:stream.write(text)
        path.write_text(yaml.safe_dump(parameters,sort_keys=False))
        changes.append(dict(robot=robot,effective_params=str(path),original_params=str(saved),previous=previous,current=values))
    with (directory/'navigation-planner-revision.json').open('x') as stream:
        json.dump(dict(revision=REVISION,launch_entry=str(Path(__file__).resolve()),
            predecessor_launch=str(HERE/'nav2_peer_geometry_launch.py'),contract=contract,
            applied_before_actions=True,changes=changes),stream,indent=2);stream.write('\n')
    return actions


def generate_launch_description():
    entities=list(base.generate_launch_description().entities)
    return LaunchDescription([OpaqueFunction(function=launch_setup) if isinstance(action,OpaqueFunction)
                              else action for action in entities])
