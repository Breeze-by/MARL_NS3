"""Offline tests of production methods; imports ROS messages but starts no node."""
import ast
from concurrent.futures import Future
import importlib.util
import itertools
import math
from pathlib import Path
import threading
from types import SimpleNamespace as NS, MethodType
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import numpy as np
from geometry_msgs.msg import Point, PointStamped, TransformStamped
from nav_msgs.msg import OccupancyGrid, Odometry
from tf2_ros import TransformException

ROOT = Path('/project')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


control = module('review_control', 'workspace/src/multi_robot_exploration/multi_robot_exploration/control.py')
merge = module('review_merge', 'workspace/src/merge_map/merge_map/merge_map.py')
runner = module('review_runner', 'tools/run_baseline.py')


def grid(data, origin=(0., 0., 0.), resolution=1.):
    result = OccupancyGrid()
    result.header.frame_id = 'map'
    result.info.height, result.info.width = np.shape(data)
    result.info.resolution = resolution
    result.info.origin.position.x, result.info.origin.position.y = origin[:2]
    result.info.origin.orientation.z = math.sin(origin[2]/2)
    result.info.origin.orientation.w = math.cos(origin[2]/2)
    result.data = np.asarray(data).ravel().tolist()
    return result


def transform(x, y, yaw):
    result = TransformStamped()
    result.transform.translation.x, result.transform.translation.y = x, y
    result.transform.rotation.z, result.transform.rotation.w = math.sin(yaw/2), math.cos(yaw/2)
    return result


def logger():
    return NS(info=lambda *_: None, warning=lambda *_: None, fatal=lambda *_: None)


class ReviewFixes(unittest.TestCase):
    def setUp(self):
        control.VISITED.clear()
        control.ASSIGNED.clear()
        control.FAILED.clear()

    def test_R1_missing_robot_and_stale_states_never_prove_stop(self):
        self.assertFalse(self.stop_scenario('missing'))
        self.assertFalse(self.stop_scenario('no_messages'))
        self.assertFalse(self.stop_scenario('frozen_clock'))
        self.assertFalse(self.stop_scenario('residual_yaw'))
        self.assertTrue(self.stop_scenario('stationary'))

    def stop_scenario(self, scenario):
        clock = NS(now=100., sim=1.)
        events = []
        observer = NS(paused_robots=set(), cancelled_goals={}, drive={r:[0.]*14 for r in runner.ROBOTS}, current_models=set(), all_models_seen=False, positions={},
            latest={}, counts={}, distances=dict.fromkeys(runner.ROBOTS, 0.),
            max_displacement=dict.fromkeys(runner.ROBOTS, 0.), max_speed=dict.fromkeys(runner.ROBOTS, 0.),
            initial_positions={}, minimum_pair_distance=math.inf, hazard=None, sim=1.,
            trajectory=NS(writerow=lambda _: None),
            event=lambda kind, **values: events.append((kind, values)),
            zero_publishers={r: NS(publish=lambda _: None) for r in runner.ROBOTS},
            call=lambda *a, **k: NS(return_code=0, goals_canceling=[], success=True))
        def seen(key):
            observer.latest[key] = clock.now
            observer.counts[key] = observer.counts.get(key, 0)+1
        observer.seen = seen
        def message(names, angular=0.):
            return NS(name=names, pose=[NS(position=NS(x=2.*i, y=0., z=0.)) for i in range(len(names))],
                      twist=[NS(linear=NS(x=0., y=0.), angular=NS(z=angular)) for _ in names])
        observer.models = MethodType(runner.Observer.models, observer)
        with patch.object(runner.time, 'monotonic', lambda: clock.now), patch.object(runner.time, 'time', lambda: clock.now):
            observer.models(message(list(runner.ROBOTS)))
            def spin(*args, **kwargs):
                clock.now += .1
                if scenario != 'frozen_clock':
                    observer.sim += .1
                for robot in runner.ROBOTS:
                    observer.drive[robot][1] += 1
                    observer.seen(robot+'/drive')
                if scenario != 'no_messages':
                    observer.models(message(list(runner.ROBOTS[:2] if scenario == 'missing' else runner.ROBOTS),
                                            .091 if scenario == 'residual_yaw' else 0.))
            with patch.object(runner.rclpy, 'spin_once', spin):
                result = runner.Observer.stop_motion(observer)
        if scenario != 'stationary':
            self.assertNotIn('observed_stop', [kind for kind, _ in events])
        if scenario == 'missing':
            self.assertNotIn('tb3', observer.positions)
        return result

    def test_R2_odometry_and_goal_transforms_nonidentity(self):
        # Local odom->map is nonidentity, and common<-map is (10,20,pi/2).
        # The composed common<-odom below maps odom (2,3) to (4,23).
        owner = NS(robot_positions={}, tf={'tb1': NS(lookup_transform=lambda *_: transform(7.,21.,math.pi/2))})
        odometry = Odometry()
        odometry.header.frame_id = 'odom'
        odometry.pose.pose.position.x, odometry.pose.pose.position.y = 2., 3.
        control.HeadquartersControl.robot_odom_callback(owner, odometry, 'tb1')
        np.testing.assert_allclose(owner.robot_positions['tb1'], (4.,23.))
        sent = []
        pending = Future()
        owner.tf['tb1'] = NS(lookup_transform=lambda *_: transform(-20.,10.,-math.pi/2))
        owner.local_maps = {'tb1':grid(np.zeros((10,10),dtype=int))}
        owner.nav_goal_in_local_map = MethodType(control.HeadquartersControl.nav_goal_in_local_map,owner)
        owner.robot_nav_clients = {'tb1': NS(wait_for_server=lambda **_: True,
            send_goal_async=lambda goal, **_: (sent.append(goal) or pending))}
        owner.feedback_callback = lambda *_: None
        owner.goal_response_callback = lambda *_: None
        owner.get_clock = lambda: NS(now=lambda: NS(to_msg=lambda: odometry.header.stamp))
        control.HeadquartersControl.send_goal(owner, 'tb1', (4.,23.))
        np.testing.assert_allclose((sent[0].pose.pose.position.x, sent[0].pose.pose.position.y), (3.,6.))
        self.assertEqual(sent[0].pose.header.frame_id, 'map')
        self.assertAlmostEqual(sent[0].pose.pose.orientation.z, -math.sqrt(.5))
        owner.tf['tb1'] = NS(lookup_transform=lambda *_: (_ for _ in ()).throw(TransformException('missing')))
        control.HeadquartersControl.robot_odom_callback(owner, odometry, 'tb1')
        self.assertNotIn('tb1', owner.robot_positions)

    def test_R2_rotated_origin_calibration_and_resolution(self):
        g = grid([[100,0]], origin=(1.,2.,math.pi/2))
        out = merge.merge_maps([g], 'merge_map', [(10.,20.,math.pi/2)])
        np.testing.assert_allclose((out.info.origin.position.x, out.info.origin.position.y), (6.,20.))
        self.assertEqual(list(out.data), [0,100])
        finer = grid([[-1]*4 for _ in range(4)], resolution=.5)
        out = merge.merge_maps([grid([[100,0],[0,0]]), finer], 'merge_map', [(0.,0.,0.)]*2)
        self.assertEqual(np.asarray(out.data).reshape(4,4)[:2,:2].tolist(), [[100,100],[100,100]])

    def test_R3_conflict_order_unknown_and_unit_origin(self):
        for values in ((0,100), (-1,100), (-1,0), (25,75)):
            outputs = [merge.merge_maps([grid([[a]]),grid([[b]])], 'merge_map', [(0.,0.,0.)]*2)
                       for a,b in (values, values[::-1])]
            self.assertEqual(outputs[0].data, outputs[1].data)
            self.assertEqual(list(outputs[0].data), [max(values)])
            self.assertEqual(outputs[0].info.origin.orientation.w, 1.)
        source = grid([[0]])
        merge.merge_maps([source], 'merge_map', [(0.,0.,0.)])
        self.assertEqual(source.header.frame_id, 'map')

    def test_R4_long_frontier_and_worker_failure(self):
        _, groups = control.assign_groups(np.full((1,1200),2))
        self.assertEqual(len(groups[1]),1200)
        shutdown = []
        owner = NS(worker_error=None, start_exploration=lambda _: (_ for _ in ()).throw(RuntimeError('injected')),
                   get_logger=logger, context=NS(try_shutdown=lambda: shutdown.append(True)))
        control.HeadquartersControl.exploration_worker(owner, 1)
        self.assertTrue(shutdown)
        self.assertIn('injected', owner.worker_error)

    def test_R4_group_order_matches_original(self):
        import subprocess
        original = subprocess.check_output(['git','--git-dir=/project/upstream/.git','show',
            '6ace727938f3e1ede3887e2c921855dc785034a1:src/multi_robot_exploration/multi_robot_exploration/control.py'],text=True)
        tree = ast.parse(original)
        selected = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('dfs','assign_groups')]
        scope = {}
        exec(compile(ast.Module(body=selected,type_ignores=[]),'original','exec'),scope)
        for seed in range(12):
            matrix = np.random.default_rng(seed).choice([0,2],size=(12,15))
            a, b = scope['assign_groups'](matrix.copy()), control.assign_groups(matrix.copy())
            self.assertEqual(a[1],b[1])
            np.testing.assert_array_equal(a[0],b[0])

    def test_R5_concavity_disconnected_cells_and_corner_cutting(self):
        cells = [(0,0),(1,0),(2,0),(2,1),(2,2),(1,2),(0,2)]
        matrix = np.zeros((5,5)); matrix[1,1] = 1
        goal = control.findClosestGroup(matrix,[(1,cells)],(4,4),1.,0.,0.,'tb1')
        row,column = int(goal[1]),int(goal[0])
        self.assertIn((row,column),cells)
        self.assertEqual(matrix[row,column],0)
        matrix = np.ones((5,5)); matrix[0,:2]=0; matrix[3:,3:]=0
        self.assertIsNone(control.findClosestGroup(matrix,[(1,[(3,3),(3,4),(4,3)])],(0,0),1.,0.,0.,'tb1'))
        self.assertEqual(control.reachable_free_cells(np.array([[0,1],[1,0]]),(0,0)),{(0,0)})

    def owner(self):
        owner = NS(robot_states={'tb1':'active'},last_successful_targets={},get_logger=logger)
        owner.release_target = MethodType(control.HeadquartersControl.release_target,owner)
        return owner

    def test_R5_goal_outside_or_occupied_local_map_is_not_sent(self):
        owner=self.owner()
        owner.local_maps={'tb1':grid([[0,100],[0,0]])}
        owner.nav_goal_in_local_map=MethodType(control.HeadquartersControl.nav_goal_in_local_map,owner)
        self.assertTrue(owner.nav_goal_in_local_map('tb1',.5,.5))
        self.assertFalse(owner.nav_goal_in_local_map('tb1',1.5,.5))
        self.assertFalse(owner.nav_goal_in_local_map('tb1',5.,.5))
        sent=[]
        owner.tf={'tb1':NS(lookup_transform=lambda *_:transform(0.,0.,0.))}
        owner.robot_nav_clients={'tb1':NS(wait_for_server=lambda **_:True,
            send_goal_async=lambda *a,**k:sent.append(a))}
        control.ASSIGNED['tb1']=(5.,.5)
        control.HeadquartersControl.send_goal(owner,'tb1',(5.,.5))
        self.assertFalse(sent)
        self.assertNotIn('tb1',control.ASSIGNED)

    def test_R6_terminal_states_reservations_and_no_completion_save(self):
        owner = self.owner()
        for status in (4,5,6):
            control.VISITED.clear(); control.ASSIGNED['tb1']=(1.,2.)
            control.HeadquartersControl.goal_result_callback(owner,'tb1',NS(status=status))
            self.assertNotIn('tb1',control.ASSIGNED)
            self.assertEqual(bool(control.VISITED),status==4)
            self.assertEqual(owner.robot_states['tb1'],'idle')
        self.assertFalse(hasattr(control.HeadquartersControl,'save_map'))
        self.assertFalse(hasattr(control.HeadquartersControl,'check_exploration_completion'))

    def test_R6_repeated_abort_no_identical_goal_loop(self):
        owner=self.owner(); target=(1.5,1.5)
        control.ASSIGNED['tb1']=target
        control.HeadquartersControl.goal_result_callback(owner,'tb1',NS(status=6))
        for _ in range(3):
            self.assertIsNone(control.findClosestGroup(np.zeros((3,3)),[(1,[(1,1)])],(0,0),1.,0.,0.,'tb1'))
        self.assertTrue(control.findClosestGroup(np.zeros((3,3)),[(1,[(1,1)])],(0,0),1.,0.,0.,'tb2'))

    def test_R6_server_unavailable_reject_and_cancel(self):
        owner=self.owner(); owner.robot_nav_clients={'tb1':NS(wait_for_server=lambda **_:False)}
        control.ASSIGNED['tb1']=(1.,2.)
        control.HeadquartersControl.send_goal(owner,'tb1',(1.,2.))
        self.assertNotIn('tb1',control.ASSIGNED)
        future=Future();future.set_result(NS(accepted=False))
        control.ASSIGNED['tb1']=(1.,2.)
        control.HeadquartersControl.goal_response_callback(owner,'tb1',future)
        self.assertNotIn('tb1',control.ASSIGNED)
        self.assertFalse(control.VISITED)

    def test_R7_smoke_predicate_all_abort_and_wall_timeout(self):
        tree=ast.parse((ROOT/'tools/run_baseline.py').read_text())
        predicate=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and
            any(isinstance(t,ast.Subscript) and isinstance(t.slice,ast.Constant) and t.slice.value=='baseline_smoke_pass' for t in n.targets))
        expr=compile(ast.Expression(predicate),'predicate','eval')
        observer=NS(hazard=None,max_displacement=dict.fromkeys(runner.ROBOTS,.2),
            statuses={r:{('g',2),('g',6)} for r in runner.ROBOTS},
            counts={r+'/feedback':1 for r in runner.ROBOTS}, map_changes=dict.fromkeys((*runner.ROBOTS,'merge_map'),2))
        result=dict(smoke_started=True,error=None,observed_stop=True,end_reason='simulation_budget')
        def valid():return eval(expr,dict(observer=observer,result=result,ROBOTS=runner.ROBOTS))
        self.assertFalse(valid())
        observer.statuses={r:{('g',2),('g',4)} for r in runner.ROBOTS}
        self.assertTrue(valid()); result['end_reason']='wall_timeout';self.assertFalse(valid())

    def test_R7_scan_and_contact_stream_freshness(self):
        now=100.
        keys=['model_states','merge_map/map']+[r+'/'+t for r in runner.ROBOTS for t in ('model_state','drive','scan','odom','map','contacts')]
        observer=NS(latest=dict.fromkeys(keys,now),tf={r:NS(can_transform=lambda *_:True) for r in runner.ROBOTS})
        with patch.object(runner.time,'monotonic',lambda:now):
            self.assertFalse(runner.Observer.ready(observer))
            for key in ('tb1/scan','tb2/contacts','tb3/map'):
                observer.latest[key]=0.
                self.assertIn(key,runner.Observer.ready(observer))

    def test_R8_dependency_metadata(self):
        for package,required in {
            'multi_robot_exploration': {'rclpy','nav_msgs','geometry_msgs','nav2_msgs','action_msgs','tf2_ros','tf2_msgs','tf2_geometry_msgs','python3-numpy'},
            'merge_map': {'rclpy','nav_msgs','python3-numpy','launch','launch_ros','ament_index_python'},
        }.items():
            xml=ET.parse(ROOT/f'workspace/src/{package}/package.xml').getroot()
            self.assertTrue(required.issubset({x.text for x in xml.findall('exec_depend')}))
            self.assertFalse(xml.findall('export/exec_depend'))


if __name__=='__main__':
    unittest.main(verbosity=2)
