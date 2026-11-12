"""NET domain placement over the original frozen scene launch, without a fork.

The NET runner must set enable_exploration:=false and enable_drive:=false;
the separate original headquarters runs in C. NET01_SESSION_ID and the frozen
GZ01_PEER_GUARD profile are required. This file does not authorize a launch.
"""
import importlib.util
import json
from pathlib import Path

from launch import LaunchDescription
from launch.actions import ExecuteProcess, GroupAction, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable
from launch.utilities import perform_substitutions
from execution_profile import load_profile

HERE=Path(__file__).resolve().parent
FROZEN_PATH=HERE.parent/'workspace/gz01/scene_launch.py'
_spec=importlib.util.spec_from_file_location('net01_frozen_scene_launch',FROZEN_PATH)
_frozen=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_frozen)


def launch_setup(context):
    original=_frozen.launch_setup(context)
    profile=load_profile(context.environment.get('NET01_EXECUTION_PROFILE') or None)
    if profile is not None:
        directory=Path(context.environment['BASE01_RUN_DIR'])
        world=directory/'effective_world.sdf'
        original_rate='<real_time_update_rate>1000</real_time_update_rate>'
        world_text=world.read_text()
        if world_text.count(original_rate)!=1:raise RuntimeError('Expected one original world wall update rate')
        world.write_text(world_text.replace(original_rate,
            f"<real_time_update_rate>{profile['world_real_time_update_rate']}</real_time_update_rate>"))
        if profile.get('controlled_physics',False):
            if context.environment.get('NET01_TIME_CONTROL')!='1':
                raise RuntimeError('Controlled physics requires its owned host sidecars')
            plugin=Path(context.environment['NET01_TIME_CONTROL_PLUGIN'])
            if not plugin.is_file():raise FileNotFoundError(plugin)
            world_text=world.read_text()
            if world_text.count('</world>')!=1:raise RuntimeError('Expected one derived world')
            world.write_text(world_text.replace('</world>',
                f'<plugin name="net01_time_control" filename="{plugin}"/></world>'))
        params=directory/'net01-clock-params.yaml'
        params.write_text(f"/gazebo:\n  ros__parameters:\n    publish_rate: {profile['clock_publish_rate_sim_hz']}\n")
        adaptation=world.with_suffix('.adaptation.json')
        metadata=json.loads(adaptation.read_text())
        metadata.update(ode_update_hz=profile['world_real_time_update_rate'],
            execution_profile=profile['id'],clock_source=dict(node='/gazebo',parameter='publish_rate',
                value=profile['clock_publish_rate_sim_hz'],params_file=str(params)))
        if profile.get('controlled_physics',False):
            metadata['controlled_time']=dict(plugin=str(plugin),initial_pause=True,
                physical_step_service='/net01/physics_step',token_steps=10)
        adaptation.write_text(json.dumps(metadata,indent=2)+'\n')
        (directory/'execution-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    merge_script=str(_frozen.PHASE/'workspace/src/merge_map/merge_map/merge_map.py')
    peer_script=str(FROZEN_PATH.with_name('peer_keepout.py'))
    session_id=context.environment['NET01_SESSION_ID']
    direct_reference=context.environment.get('NET01_DIRECT_REFERENCE')=='1'
    placed=[];counts={'merge':0,'peer':0}
    for action in original:
        if profile is not None and isinstance(action,IncludeLaunchDescription) and 'world' in dict(action.launch_arguments):
            action=IncludeLaunchDescription(action.launch_description_source,
                launch_arguments=[*action.launch_arguments,('params_file',str(params)),
                    *([('pause','true')] if profile.get('controlled_physics',False) else [])])
        # Only the original plain ExecuteProcess commands are inspected. Node
        # command substitutions remain deferred to their original execution.
        if type(action) is ExecuteProcess:
            command=[perform_substitutions(context,part) for part in action.cmd]
            if len(command)>2 and command[2] in (merge_script,peer_script):
                if command[2]==merge_script:
                    counts['merge']+=1
                else:
                    counts['peer']+=1
                    command[2]=str(HERE/'bound_peer.py')
                    index=command.index('--ros-args')
                    command[index:index]=['--session-id',session_id]
                    if profile is not None:
                        command[index:index]=['--execution-profile',profile['id']]
                    if context.environment.get('NET01_DISPATCH_PROFILE')=='1':
                        command[index:index]=['--health-trace']
                    action=ExecuteProcess(cmd=command,output='screen')
                placed.append(GroupAction(actions=[
                    SetEnvironmentVariable('ROS_DOMAIN_ID','92' if direct_reference else '91'),action],
                    scoped=True,forwarding=True))
                continue
        placed.append(action)
    if counts!={'merge':1,'peer':1}:
        raise RuntimeError(f'Expected original merge and peer launch points, got {counts}')
    return placed


def generate_launch_description():
    original=_frozen.generate_launch_description()
    entities=list(original.entities)
    if sum(isinstance(action,OpaqueFunction) for action in entities)!=1:
        raise RuntimeError('Expected one original scene launch_setup OpaqueFunction')
    # A persistent R default also covers delayed OnProcessExit child actions;
    # an outer scoped group could pop before those callbacks are dispatched.
    return LaunchDescription([SetEnvironmentVariable('ROS_DOMAIN_ID','92'),*[
        OpaqueFunction(function=launch_setup) if isinstance(action,OpaqueFunction) else action
        for action in entities]])
