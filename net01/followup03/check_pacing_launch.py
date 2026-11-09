"""One no-Node launch-generation check; never starts LaunchService/processes."""
import argparse
import json
import os
from pathlib import Path
import sys
import yaml
from launch import LaunchContext
from launch.actions import IncludeLaunchDescription
from launch.utilities import normalize_to_list_of_substitutions,perform_substitutions

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import net_scene_launch as net
from execution_profile import PROFILE_ID

parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
a=parser.parse_args();a.output.mkdir(exist_ok=False)
os.environ.update(BASE01_RUN_DIR=str(a.output),GZ01_PEER_GUARD='1',NET01_SESSION_ID='2026110916',NET01_EXECUTION_PROFILE=PROFILE_ID)
context=LaunchContext();context.launch_configurations.update(dict(robot_count='3',scene='/mnt/inputs/scenes/regression-corridor-common-6201-dwb-v1.json',use_sim_time='true',enable_drive='false',enable_rviz='false',enable_gui='false',enable_exploration='false',nav2_autostart='false',nav2_log_level='warn',drive_plugin='libbase01_diff_drive.so'))
context.environment.update(os.environ)
original_setup=net._frozen.launch_setup
captured={}
def capture(ctx):
    actions=original_setup(ctx)
    captured['world']=(a.output/'effective_world.sdf').read_bytes()
    captured['yaml']={p.name:p.read_bytes() for p in a.output.glob('*.yaml')}
    return actions
net._frozen.launch_setup=capture
actions=net.launch_setup(context)
world=(a.output/'effective_world.sdf').read_bytes()
metadata=json.loads((a.output/'effective_world.adaptation.json').read_text())
clock=a.output/'net01-clock-params.yaml'
args=[]
for action in actions:
    if isinstance(action,IncludeLaunchDescription):
        values={perform_substitutions(context,normalize_to_list_of_substitutions(k)):perform_substitutions(context,normalize_to_list_of_substitutions(v)) for k,v in action.launch_arguments}
        args.append(values)
servers=[x for x in args if 'world' in x]
checks=dict(world_only_wall_rate_changed=world==captured['world'].replace(b'<real_time_update_rate>1000</real_time_update_rate>',b'<real_time_update_rate>500</real_time_update_rate>'),original_rate_present_once=captured['world'].count(b'<real_time_update_rate>1000</real_time_update_rate>')==1,metadata_rate_matches=metadata['ode_update_hz']==500,metadata_dt_unchanged=metadata['ode_step_s']==.001,metadata_profile=metadata['execution_profile']==PROFILE_ID,metadata_clock_source=metadata['clock_source']==dict(node='/gazebo',parameter='publish_rate',value=100.0,params_file=str(clock)),scoped_clock_yaml=yaml.safe_load(clock.read_text())=={'/gazebo':{'ros__parameters':{'publish_rate':100.0}}},one_gzserver=len(servers)==1,gzserver_params_scoped=len(servers)==1 and servers[0]['params_file']==str(clock),other_includes_no_clock_params=all(x.get('params_file')!=str(clock) for x in args if 'world' not in x),original_nav2_slam_yamls_unchanged=all((a.output/name).read_bytes()==raw for name,raw in captured['yaml'].items()),original_three_nav2_configs=len([name for name in captured['yaml'] if name.startswith('peer_nav2_')])==3)
result=dict(scope='Only launch description generation; 0Node/0LaunchService/0GZ/0Goal/0NN',checks=checks,all_pass=all(checks.values()),gzserver_arguments=servers,unchanged_yaml_names=sorted(captured['yaml']))
(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
raise SystemExit(0 if result['all_pass'] else 1)
