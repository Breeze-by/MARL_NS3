#!/usr/bin/env python3
import os
import json
import math
import xml.etree.ElementTree as ET
import yaml
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, RegisterEventHandler, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch.actions import IncludeLaunchDescription, ExecuteProcess, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.event_handlers import OnProcessExit
from launch.conditions import IfCondition


PHASE = Path(__file__).resolve().parents[2]
PHYSICS_ADAPTER = 'base01-ground-contact-v1'
# Exact accepted Econ ground contact settings; generated maps omitted surface.
GROUND_SURFACE = """<surface>
  <contact><collide_bitmask>65535</collide_bitmask><ode /></contact>
  <friction><ode><mu>100</mu><mu2>50</mu2></ode><torsional><ode /></torsional></friction>
  <bounce />
</surface>"""
ODE_PHYSICS = """<physics type='ode'>
  <max_step_size>0.001</max_step_size><real_time_factor>1</real_time_factor>
  <real_time_update_rate>1000</real_time_update_rate>
</physics>"""


def load_scene(path):
    """One declared calibration drives physical spawn, merge and robot TF."""
    scene = json.loads(Path(path).read_text())
    relative = Path(scene['world_relative_phase'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Scene world must be phase relative')
    scene['world_path'] = PHASE/relative
    if [r['name'] for r in scene['robots']] != ['tb1', 'tb2', 'tb3']:
        raise ValueError('Scene must declare tb1/tb2/tb3 in order')
    for robot in scene['robots']:
        if not all(math.isfinite(robot[key]) for key in ('x', 'y', 'yaw')):
            raise ValueError('Non-finite scene spawn')
        if robot['yaw'] != 0 and not scene.get('controlled_stop_diagnostic',False):
            raise ValueError('This GZ-01 batch declares zero spawn yaw')
    if any(math.hypot(a['x']-b['x'], a['y']-b['y']) < .70
           for i,a in enumerate(scene['robots']) for b in scene['robots'][i+1:]):
        raise ValueError('Scene violates existing 0.70m pair separation')
    if type(scene['physics_seed']) is not int or scene['physics_seed'] < 0:
        raise ValueError('Scene requires a nonnegative integer Gazebo physics seed')
    return scene


def monitored_world(source, destination, solver_iterations=None, solver_type='quick'):
    """Restore accepted floor contact, lock existing ODE defaults, add observer."""
    text = Path(source).read_text()
    root = ET.fromstring(text)
    world = root.find('world')
    if world is None:
        raise ValueError('Scene SDF has no world')
    changed = False
    ground = world.find("model[@name='ground_plane']/link/collision")
    if ground.find('surface') is None:
        ground.append(ET.fromstring(GROUND_SURFACE))
        changed = True
    if world.find('physics') is None:
        world.append(ET.fromstring(ODE_PHYSICS))
        changed = True
    if solver_iterations is not None or solver_type=='world':
        # Explicit single-variable numerical-accuracy candidate; no contact change.
        ode = ET.SubElement(world.find('physics'), 'ode')
        solver = ET.SubElement(ode, 'solver')
        ET.SubElement(solver, 'type').text = solver_type
        if solver_iterations is not None:
            ET.SubElement(solver, 'iters').text = str(solver_iterations)
        ET.SubElement(solver, 'sor').text = '1.3'
        changed = True
    if not any(p.get('filename') == 'libgazebo_ros_state.so' for p in world.findall('plugin')):
        world.append(ET.fromstring("""
        <plugin name='gz01_observer_state' filename='libgazebo_ros_state.so'>
          <ros><namespace>/gazebo</namespace></ros><update_rate>10.0</update_rate>
        </plugin>"""))
        changed = True
    if 'GZ01_PHASE_PROBE_LIBRARY' in os.environ:
        probe = ET.SubElement(world, 'plugin', name='gz01_phase_probe',
                              filename=os.environ['GZ01_PHASE_PROBE_LIBRARY'])
        ET.SubElement(probe, 'output').text = str(Path(destination).with_name('physics-phase.csv'))
        changed = True
    if not changed:
        return source
    # Only missing non-geometric elements change; source worlds stay immutable.
    ET.indent(root)
    with Path(destination).open('x') as stream:
        stream.write(ET.tostring(root,encoding='unicode'))
    Path(destination).with_suffix('.adaptation.json').write_text(json.dumps(dict(
        version=PHYSICS_ADAPTER+('-ode-world' if solver_type=='world' else '-ode200' if solver_iterations is not None else ''),source=str(source),effective=str(destination),
        ground_mu=100,ground_mu2=50,ode_step_s=.001,ode_update_hz=1000,
        ode_solver=solver_type,ode_solver_iterations=solver_iterations,ode_sor=1.3,
        driver_changed=False,geometry_changed=False),indent=2)+'\n')
    return destination


def tire_slip_model(source, destination, slip):
    """One contact-compliance candidate; original robot remains immutable."""
    root=ET.parse(source).getroot()
    for name in ('wheel_left_link','wheel_right_link'):
        ode=root.find("model/link[@name='"+name+"']/collision/surface/friction/ode")
        for key in ('slip1','slip2'):
            ode.find(key).text=str(slip)
    ET.indent(root)
    with Path(destination).open('x') as stream:
        stream.write(ET.tostring(root,encoding='unicode'))
    Path(destination).with_suffix('.adaptation.json').write_text(json.dumps(dict(
        version='tire-slip-v1',source=str(source),effective=str(destination),
        wheel_slip_mps_per_N=slip,changed_links=['wheel_left_link','wheel_right_link'],
        friction_caps_changed=False,driver_changed=False,geometry_changed=False),indent=2)+'\n')
    return destination


def slam_parameters(source, destination, namespace):
    """Case-local copy; retain SLAM except the reviewed loop acceptance gate."""
    params=yaml.safe_load(Path(source).read_text().replace('$(var namespace)',namespace))
    params[namespace+'/slam_toolbox']['ros__parameters']['loop_match_minimum_response_fine']=.75
    with Path(destination).open('x') as stream:yaml.safe_dump(params,stream,sort_keys=False)
    return str(destination)


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('robot_count', default_value='3'),
        DeclareLaunchArgument('scene', description='Reviewed scene JSON; world path relative to phase root'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('enable_drive', default_value='false'),
        DeclareLaunchArgument('enable_rviz', default_value='true'),
        DeclareLaunchArgument('enable_gui', default_value='true'),
        DeclareLaunchArgument('enable_exploration', default_value='true'),
        DeclareLaunchArgument('nav2_autostart', default_value='true'),
        DeclareLaunchArgument('nav2_log_level', default_value='warn'),
        DeclareLaunchArgument('drive_plugin', default_value='libbase01_diff_drive.so'),
        OpaqueFunction(function=launch_setup),
    ])


def launch_setup(context):
    ld = LaunchDescription()

    scene = load_scene(Path(LaunchConfiguration('scene').perform(context)))
    robots = [dict(name=r['name'], x_pose=str(r['x']), y_pose=str(r['y']), yaw=r['yaw'])
              for r in scene['robots']]
    robot_count = LaunchConfiguration('robot_count')
    if int(robot_count.perform(context)) != 3:
        raise ValueError('GZ-01 requires exactly three Waffle robots')
    use_sim_time = LaunchConfiguration('use_sim_time')
    # Simulation scenario calibration: declared spawn poses, never live world poses.
    map_poses = [float(robot[key]) for robot in robots for key in ('x_pose', 'y_pose', 'yaw')]
    
    # Execute this reviewed worktree source; the BASE installation remains immutable.
    merge_map_launch = ExecuteProcess(
        cmd=['python3', '-B', str(PHASE/'workspace/src/merge_map/merge_map/merge_map.py'),
             '--ros-args', '-r', '__node:=merge_map',
             '-p', 'robot_count:='+str(len(robots)), '-p', 'frame_id:=merge_map',
             '-p', 'map_poses:='+str(map_poses), '-p', 'use_sim_time:=true',
             '-p', 'output_grid_resolution:=0.05'],
        output='screen'
    )
    ld.add_action(merge_map_launch)
    if 'GZ01_PEER_GUARD' in os.environ:
        ld.add_action(ExecuteProcess(cmd=['python3','-B',str(Path(__file__).with_name('peer_keepout.py')),
            '--scene',str(LaunchConfiguration('scene').perform(context)),
            '--directory',os.environ['BASE01_RUN_DIR'],*(['--timing'] if scene.get('peer_timing',False) else []),
            '--ros-args','-p','use_sim_time:=true'],output='screen'))

    # Launch multi_robot_exploration control with robot_count argument
    control_node = ExecuteProcess(
        cmd=['ros2', 'run', 'multi_robot_exploration', 'control', '--ros-args',
             '-p', ['robot_count:=', robot_count], '-p', ['use_sim_time:=', use_sim_time]],
        output='screen',
        condition=IfCondition(LaunchConfiguration('enable_exploration')),
    )
    ld.add_action(control_node)

    MY_ROBOT = 'turtlebot3_waffle'

    enable_drive = LaunchConfiguration('enable_drive', default='false')
    enable_rviz = LaunchConfiguration('enable_rviz', default='true')
    multi_robot = get_package_share_directory('multi_robot')
    ld.add_action(SetEnvironmentVariable(
        'GAZEBO_MODEL_PATH', os.path.join(multi_robot, 'models') + os.pathsep +
        os.environ.get('GAZEBO_MODEL_PATH', '')))
    
    package_dir = get_package_share_directory('multi_robot')
    nav_launch_dir = os.path.join(package_dir, 'launch', 'nav2_bringup')

    urdf = os.path.join(
        multi_robot, 'urdf', MY_ROBOT + '.urdf'
    )
    model = os.path.join(
        multi_robot,'models', MY_ROBOT, 'model.sdf'
    )

    drive_plugin = LaunchConfiguration('drive_plugin').perform(context)
    if drive_plugin not in ('libbase01_diff_drive.so', 'libbase01_diff_drive_diagnostic.so'):
        raise ValueError('Unsupported BASE-01 drive plugin')
    if drive_plugin != 'libbase01_diff_drive.so':
        effective_model = Path(os.environ['BASE01_RUN_DIR']) / 'effective_robot.sdf'
        effective_model.write_text(Path(model).read_text().replace('libbase01_diff_drive.so', drive_plugin))
        model = str(effective_model)
    if 'wheel_contact_slip' in scene:
        model=str(tire_slip_model(model,
            Path(os.environ['BASE01_RUN_DIR'])/'effective_contact_robot.sdf',scene['wheel_contact_slip']))

    world = str(monitored_world(scene['world_path'], Path(os.environ['BASE01_RUN_DIR'])/'effective_world.sdf',
                               scene.get('ode_solver_iterations'),scene.get('ode_solver_type','quick')))

    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            str(Path(__file__).with_name('batch_gzserver.launch.py')) if os.environ.get('GZ01_BATCH_GDB') == '1' else
                os.path.join(get_package_share_directory('gazebo_ros'), 'launch', 'gzserver.launch.py')
        ),
        launch_arguments={'world': world, 'seed': str(scene['physics_seed'])}.items(),
    )

    gzclient_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('gazebo_ros'), 'launch', 'gzclient.launch.py')
        ),
        condition=IfCondition(LaunchConfiguration('enable_gui')),
    )

    ld.add_action(gzserver_cmd)
    ld.add_action(gzclient_cmd)

    remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]
    
    last_action = None
    # Spawn turtlebot3 instances in gazebo
    for robot in robots:
        namespace =  [ '/' + robot['name'] ]
        
        params_file = os.path.join(get_package_share_directory('multi_robot'), 'params', f"nav2_params_{robot['name']}_0.yaml")
        if 'GZ01_PEER_GUARD' in os.environ:
            params=yaml.safe_load(Path(params_file).read_text())
            # Global planning follows actual SLAM map extent; local stays rolling.
            params['global_costmap']['global_costmap']['ros__parameters']['rolling_window']=False
            for layer in ('global_costmap','local_costmap'):
                settings=params[layer][layer]['ros__parameters']
                settings['filters']=['peer_keepout']
                settings['peer_keepout']=dict(plugin='nav2_costmap_2d::KeepoutFilter',enabled=True,
                    filter_info_topic=f"/{robot['name']}/peer_keepout_filter_info",transform_tolerance=.2)
            if scene.get('rotation_shim',False):
                follow_path=params['controller_server']['ros__parameters']['FollowPath']
                follow_path['primary_controller']=follow_path['plugin']
                follow_path['plugin']='nav2_rotation_shim_controller::RotationShimController'
                follow_path.update(angular_dist_threshold=math.pi/4,
                    angular_disengage_threshold=math.pi/4,forward_sampling_distance=.5,
                    rotate_to_heading_angular_vel=.6,max_angular_accel=3.2,
                    simulate_ahead_time=1.7,closed_loop=True,rotate_to_goal_heading=False)
            generated=Path(os.environ['BASE01_RUN_DIR'])/f"peer_nav2_{robot['name']}.yaml"
            with generated.open('x') as stream:yaml.safe_dump(params,stream,sort_keys=False)
            params_file=str(generated)
        print(f"Namespace: {namespace}, PARAM Config: {params_file}\n\n")
        
        # Create state publisher node for that instance
        robot_state_publisher = Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            namespace=namespace,
            output='screen',
            parameters=[{'use_sim_time': use_sim_time, 'publish_frequency': 10.0}],
            remappings=remappings,
            arguments=[urdf],
        )
        
        # Joint State Publisher node
        joint_state_publisher_node = Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            namespace=namespace,
            name='joint_state_publisher',
            parameters=[{'use_sim_time':use_sim_time}],
            remappings=remappings,
        )

        # Create spawn call
        spawn_robot = Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            arguments=[
                '-file', model,
                '-entity', robot['name'],
                '-robot_namespace', namespace,
                '-x', robot['x_pose'], '-y', robot['y_pose'],
                '-z', '0.01', '-Y', str(robot['yaw']), '-R', '0.0', '-P', '0.0',
            ],
            output='screen',
        )
        map_file_path = os.path.join(
        multi_robot,
        '../../../../src/multi_robot/maps/turtlebot3_world.yaml')

        bringup_cmd = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory('multi_robot'), 'launch', 'nav2_bringup', 'bringup_launch.py')),
                launch_arguments={
                    'slam': 'True',
                    'namespace': namespace,
                    'use_namespace': 'True',
                    'map': map_file_path,
                    'map_server': 'False',
                    'params_file': params_file,
                    'default_bt_xml_filename': os.path.join(
                        get_package_share_directory('nav2_bt_navigator'),
                        'behavior_trees', 'navigate_to_pose_w_replanning_and_recovery.xml'),
                    'autostart': LaunchConfiguration('nav2_autostart'),
                    'use_sim_time': use_sim_time, 'log_level': LaunchConfiguration('nav2_log_level')}.items())
        
        slam_config=slam_parameters(
            Path(get_package_share_directory('slam_toolbox'))/'config/mapper_params_online_multi_async.yaml',
            Path(os.environ['BASE01_RUN_DIR'])/f"slam_{robot['name']}.yaml",'/'+robot['name'])
        # Same installed Node, name, namespace, remaps and insertion order as the
        # original online_async_multirobot_launch.py; only fine gate is changed.
        slam_toolbox_node = Node(package='slam_toolbox',executable='multirobot_slam_toolbox_node',
            name='slam_toolbox',namespace=namespace,output='screen',
            remappings=[('/map','map'),('/tf','tf'),('/tf_static','tf_static'),('/map_metadata','map_metadata')],
            parameters=[slam_config,{'use_sim_time': True}])
        
        
        node_tf_map_to_odom = Node(
            package='tf2_ros', executable='static_transform_publisher',
            namespace=namespace, remappings=remappings,
            arguments=['--x', robot['x_pose'], '--y', robot['y_pose'], '--yaw', str(robot['yaw']),
                       '--frame-id', 'merge_map', '--child-frame-id', 'map'],
            parameters=[{'use_sim_time': use_sim_time}], output='screen')

        if last_action is None:
            # Call add_action directly for the first robot
            ld.add_action(robot_state_publisher)
            ld.add_action(spawn_robot)
            ld.add_action(bringup_cmd)
            # ld.add_action(robot_localization_node)
            ld.add_action(joint_state_publisher_node)
            ld.add_action(node_tf_map_to_odom)
            ld.add_action(slam_toolbox_node)
        else:
            # Ensure next robot creation happens only after the previous one is completed
            spawn_robot_event = RegisterEventHandler(
                event_handler=OnProcessExit(
                    target_action=last_action,
                    on_exit=[spawn_robot, 
                             robot_state_publisher, 
                             joint_state_publisher_node, 
                             node_tf_map_to_odom, 
                             slam_toolbox_node, 
                             bringup_cmd
                             ],
                )
            )
            ld.add_action(spawn_robot_event)

        # Save last instance for the next RegisterEventHandler
        last_action = spawn_robot
    

    for robot in robots:
        namespace =  [ '/' + robot['name']]

        rviz_config_file_ = os.path.join(get_package_share_directory('multi_robot'), 'rviz', f"multi_robot_maping_{robot['name']}.rviz")

        print(f"Namespace: {namespace}, RViz Config: {rviz_config_file_}\n\n")
        
        rviz_cmd = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(nav_launch_dir, 'rviz_launch.py')),
                launch_arguments={'use_sim_time': use_sim_time, 
                                  'namespace': namespace,
                                  'use_namespace': 'True',
                                  'rviz_config': rviz_config_file_, 'log_level': 'warn'}.items(),
                                   condition=IfCondition(enable_rviz)
                                    )

        drive_turtlebot3 = Node(
            package='turtlebot3_gazebo', executable='turtlebot3_drive',
            namespace=namespace, output='screen',
            condition=IfCondition(enable_drive),
        )

        # Ensure initial pose and drive nodes start only after robots are spawned
        post_spawn_event = RegisterEventHandler(
            event_handler=OnProcessExit(
                target_action=last_action,
                on_exit=[rviz_cmd, drive_turtlebot3],
            )
        )
        
        ld.add_action(post_spawn_event)

    return list(ld.entities)
