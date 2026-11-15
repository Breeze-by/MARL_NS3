"""NET domain placement over the original frozen scene launch, without a fork.

The NET runner must set enable_exploration:=false and enable_drive:=false;
the separate original headquarters runs in C. NET01_SESSION_ID and the frozen
GZ01_PEER_GUARD profile are required. This file does not authorize a launch.
"""
import importlib.util
import json
from pathlib import Path
import re
import socket
import time
import xml.etree.ElementTree as ET

from launch import LaunchDescription
from launch.actions import ExecuteProcess, GroupAction, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable, RegisterEventHandler
from launch.event_handlers import OnProcessExit, OnProcessStart
from launch.utilities import perform_substitutions
from execution_profile import load_profile

HERE=Path(__file__).resolve().parent
FROZEN_PATH=HERE.parent/'workspace/gz01/scene_launch.py'
_spec=importlib.util.spec_from_file_location('net01_frozen_scene_launch',FROZEN_PATH)
_frozen=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_frozen)


def spawn_gated_setup(context,profile):
    """Observe original spawn actions/exits; never replace their arguments."""
    original_node=_frozen.Node
    spawns={}
    def capture(*args,**kwargs):
        action=original_node(*args,**kwargs)
        if kwargs.get('package')=='gazebo_ros' and kwargs.get('executable')=='spawn_entity.py':
            arguments=kwargs['arguments'];robot=arguments[arguments.index('-entity')+1]
            if robot in spawns:raise RuntimeError('Duplicate original spawn entity: '+robot)
            spawns[robot]=action
        return action
    _frozen.Node=capture
    try:actions=_frozen.launch_setup(context)
    finally:_frozen.Node=original_node
    if set(spawns)!={'tb1','tb2','tb3'}:raise RuntimeError('Expected exactly three original spawn actions')
    directory=Path(context.environment['BASE01_RUN_DIR'])
    path=directory/'startup-spawn-events.jsonl'
    path.open('x').close()
    exits={};query_started=False
    session=int(context.environment['NET01_SESSION_ID'])
    address=str(Path(context.environment['NET01_TIME_CONTROL_DIRECTORY'])/'ack.sock')
    def record(row):
        with path.open('a') as stream:stream.write(json.dumps(row)+'\n')
    def factory_fence():
        world_name=ET.parse(directory/'effective_world.sdf').getroot().find('world').attrib['name']
        command=['gz','model','-w',world_name,'-m','tb3','-i']
        query=ExecuteProcess(cmd=command,name='startup_factory_cycle_fence',
            output='log',cached_output=True)
        fence=dict(request='entity_info',world_name=world_name,model_name='tb3',command=command,
            requested_monotonic_ns=time.monotonic_ns(),requested_realtime_ns=time.time_ns(),
            timestamp_scope='CLI process admission/start/exit brackets; exact native request send/response timestamps unmeasured')
        def started(event,ctx):
            fence.update(pid=event.pid,started_monotonic_ns=time.monotonic_ns(),started_realtime_ns=time.time_ns())
            record(dict(kind='factory_fence_process_started',**fence))
        def completed(event,ctx):
            stdout=query.get_stdout();stderr=query.get_stderr()
            (directory/'startup-factory-fence.stdout').write_text(stdout)
            (directory/'startup-factory-fence.stderr').write_text(stderr)
            names=re.findall(r'^name: "([^"\n]+)"$',stdout,re.MULTILINE)
            fence.update(pid=event.pid,returncode=event.returncode,
                exited_monotonic_ns=time.monotonic_ns(),exited_realtime_ns=time.time_ns(),
                response_model_name=names[0] if names==['tb3'] else None)
            passed=event.returncode==0 and names==['tb3']
            record(dict(kind='factory_fence_process_exited',passed=passed,**fence))
            if not passed:return
            ready=dict(kind='startup_spawn_ready',session_id=session,execution_profile=profile['id'],
                monotonic_ns=time.monotonic_ns(),realtime_ns=time.time_ns(),factory_fence=fence,
                spawns=[dict(robot=r,pid=exits[r]['pid'],returncode=exits[r]['returncode'],
                    exit_monotonic_ns=exits[r]['monotonic_ns'],exit_realtime_ns=exits[r]['realtime_ns'])
                    for r in ('tb1','tb2','tb3')])
            with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as channel:
                channel.setblocking(False);channel.sendto(json.dumps(ready).encode(),address)
            record(dict(kind='startup_spawn_ready_sent',payload=ready,monotonic_ns=time.monotonic_ns(),
                realtime_ns=time.time_ns(),control_socket=address,business_payload=False))
        return [RegisterEventHandler(OnProcessStart(target_action=query,on_start=started)),
            RegisterEventHandler(OnProcessExit(target_action=query,on_exit=completed)),query]
    def exited(robot,event,launch_context):
        nonlocal query_started
        row=dict(kind='original_spawn_entity_exit',robot=robot,pid=event.pid,
            returncode=event.returncode,monotonic_ns=time.monotonic_ns(),realtime_ns=time.time_ns(),
            session_id=session,execution_profile=profile['id'],actual_command=event.cmd,
            duplicate=robot in exits)
        record(row)
        if robot in exits:return
        exits[robot]=row
        if len(exits)!=3 or any(r['returncode']!=0 for r in exits.values()) or query_started:return
        query_started=True
        return factory_fence()
    # Register before any original process can exit, including the first spawn.
    handlers=[RegisterEventHandler(OnProcessExit(target_action=action,
        on_exit=lambda event,ctx,robot=robot:exited(robot,event,ctx)))
        for robot,action in spawns.items()]
    return [*handlers,*actions]


def launch_setup(context):
    profile=load_profile(context.environment.get('NET01_EXECUTION_PROFILE') or None)
    original=(spawn_gated_setup(context,profile)
        if profile is not None and profile.get('startup_spawn_gate',{}).get('id')=='all-spawn-exit0-factory-cycle-fence-v1'
        else _frozen.launch_setup(context))
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
