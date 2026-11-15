"""Only new A0 tuning tasks: original launch, then six generated inflation keys."""
import importlib.util
import json
from pathlib import Path

from launch import LaunchDescription
from launch.actions import OpaqueFunction
import yaml
from clearance_tuning import CONTRACT,ENV,REVISION,set_inflation_parameters,validate_contract
from execution_profile import load_profile

REPO=Path(__file__).resolve().parent.parent
PREDECESSOR=REPO/'net01/nav2_simclock_launch.py'
spec=importlib.util.spec_from_file_location('clearance_original_simclock_launch',PREDECESSOR)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)


def launch_setup(context):
    profile=load_profile(context.environment['NET01_EXECUTION_PROFILE'])
    validate_contract(json.loads(context.environment[ENV]),profile['id'],context.environment.get('NET01_DIRECT_REFERENCE')=='1')
    actions=base.launch_setup(context)
    directory=Path(context.environment['BASE01_RUN_DIR']);changes=[]
    for robot in ('tb1','tb2','tb3'):
        path=directory/f'peer_nav2_{robot}.yaml';text=path.read_text();parameters=yaml.safe_load(text)
        altered=set_inflation_parameters(parameters)
        before=directory/f'peer_nav2_{robot}.before-clearance-tuning.yaml'
        with before.open('x') as stream:stream.write(text)
        path.write_text(yaml.safe_dump(parameters,sort_keys=False))
        changes.append(dict(robot=robot,effective_params=str(path),before_params=str(before),changes=altered))
    with (directory/'navigation-clearance-revision.json').open('x') as stream:
        json.dump(dict(revision=REVISION,contract=CONTRACT,launch_entry=str(Path(__file__).resolve()),
            predecessor=str(PREDECESSOR),applied_before_actions=True,changes=changes,
            common_execution_revision_unchanged='nav2-simclock-common-v1',
            scope='Only six inflation_radius keys changed; original robot_radius, scaling, physical model, policy701, candidate/goal/clock/stop contracts retained'),stream,indent=2)
        stream.write('\n')
    return actions


def generate_launch_description():
    return LaunchDescription([OpaqueFunction(function=launch_setup) if isinstance(action,OpaqueFunction)
        else action for action in base.generate_launch_description().entities])
