"""Static/no-Node GZ-01 fixture. Never imports ROS, torch or a real model."""
import ast
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent


def tree(path):
    return ast.parse(path.read_text())


def definition(path,name):
    return next(node for node in tree(path).body if isinstance(node,(ast.ClassDef,ast.FunctionDef)) and node.name==name)


def extract(path,names,namespace):
    module = ast.Module(body=[definition(path,n) for n in names],type_ignores=[])
    exec(compile(ast.fix_missing_locations(module),str(path),'exec'),namespace)
    return namespace


class RunnerStatic(unittest.TestCase):
    def test_original_stop_and_observer_ast_identical(self):
        for name in ('Observer','end_process'):
            self.assertEqual(ast.dump(definition(HERE/'run_case.py',name)),
                             ast.dump(definition(WORKSPACE/'rl02/run_gazebo.py',name)))

    def test_common_pipeline_only_expected_traditional_rejection_difference(self):
        original = next(n for n in definition(WORKSPACE/'rl01/ros_policy.py','CheckpointHeadquarters').body
                        if isinstance(n,ast.FunctionDef) and n.name=='allocate_once')
        common = next(n for n in definition(HERE/'headquarters.py','GZHeadquarters').body
                      if isinstance(n,ast.FunctionDef) and n.name=='allocate_common')
        original.name = 'allocate_common'
        rejected = next(n for n in ast.walk(original) if isinstance(n,ast.If)
                        and isinstance(n.test,ast.Name) and n.test.id=='rejected')
        rejected.test = ast.parse("rejected and self.arm == 'rl'",mode='eval').body
        self.assertEqual(ast.dump(original),ast.dump(common))
        base = definition(HERE/'headquarters.py','GZHeadquarters')
        self.assertEqual(base.bases[0].id,'RL04Headquarters')

    def test_scene_spawn_calibration_and_observation_plugin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            world = root/'world.sdf'
            world.write_text("<sdf version='1.7'><world name='test'><model name='ground_plane'>"
                "<link name='ground'><collision name='ground'><geometry><plane><normal>0 0 1</normal>"
                "<size>100 100</size></plane></geometry></collision></link></model>"
                "<model name='wall'><static>true</static></model></world></sdf>")
            scene = root/'scene.json'
            scene.write_text(json.dumps(dict(world_relative_phase='world.sdf',physics_seed=701,
                robots=[dict(name='tb1',x=-2.,y=0.,yaw=0),dict(name='tb2',x=0.,y=0.,yaw=0),dict(name='tb3',x=2.,y=0.,yaw=0)])))
            constants = {n.targets[0].id:ast.literal_eval(n.value)
                         for n in tree(HERE/'scene_launch.py').body if isinstance(n,ast.Assign)
                         and isinstance(n.targets[0],ast.Name)
                         and n.targets[0].id in ('GROUND_SURFACE','ODE_PHYSICS','PHYSICS_ADAPTER')}
            ns = extract(HERE/'scene_launch.py',('load_scene','monitored_world'),
                         dict(Path=Path,json=json,math=math,ET=ET,PHASE=root,**constants))
            loaded = ns['load_scene'](scene)
            self.assertEqual(loaded['world_path'],world)
            effective = root/'effective.sdf'
            ns['monitored_world'](world,effective)
            parsed = ET.fromstring(effective.read_text())
            plugin = parsed.find('world/plugin')
            self.assertEqual(plugin.get('filename'),'libgazebo_ros_state.so')
            parsed.find('world').remove(plugin)
            ground=parsed.find("world/model[@name='ground_plane']/link/collision")
            surface=ground.find('surface');physics=parsed.find('world/physics')
            baseline=ET.parse(HERE.parents[2]/'base-01-econ/workspace/src/multi_robot/worlds/my_world.world')
            def canonical(element):
                return ET.canonicalize(ET.tostring(element,encoding='unicode'),strip_text=True)
            self.assertEqual(canonical(surface),canonical(baseline.find(
                "world/model[@name='ground_plane']/link/collision/surface")))
            self.assertEqual(canonical(physics),canonical(baseline.find('world/physics')))
            ground.remove(surface);parsed.find('world').remove(physics)
            self.assertEqual(canonical(parsed),canonical(ET.fromstring(world.read_text())))
            self.assertEqual(ns['monitored_world'](effective,root/'unused.sdf'),effective)
            bad = json.loads(scene.read_text());bad['robots'][1]['x']=-1.8
            scene.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'separation'):
                ns['load_scene'](scene)
        launch = (HERE/'scene_launch.py').read_text()
        self.assertIn("'seed': str(scene['physics_seed'])",launch)
        self.assertIn("'-Y', str(robot['yaw'])",launch)
        self.assertIn("for key in ('x_pose', 'y_pose', 'yaw')",launch)

    def test_budget_terminal_not_natural_or_threshold(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            ns = extract(HERE/'run_case.py',('controller_end',),dict(json=json))
            self.assertEqual(ns['controller_end'](directory,0),(None,0))
            (directory/'allocation-events.jsonl').write_text(json.dumps(dict(kind='rl_halt_requested',reason='decision_budget'))+'\n{')
            self.assertEqual(ns['controller_end'](directory,0)[0],'decision_budget')
        source = (HERE/'run_case.py').read_text()
        self.assertIn('natural_complete=False, threshold_reached=None',source)
        self.assertIn("return 0 if result['run_integrity'] else 1",source)
        self.assertNotIn('import metrics',source)

    def test_no_ready_no_admission(self):
        spec = importlib.util.spec_from_file_location('gz01_boot_fixture',HERE/'boot.py')
        boot = importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)
        with tempfile.TemporaryDirectory() as temp:
            ready = Path(temp)/'ready.json';ready.write_text('{}')
            with self.assertRaisesRegex(ValueError,'No root-reviewed'):
                boot.validate_ready(ready)

    def test_terminal_cursor_reuses_history_and_completes_partial_record(self):
        ns = extract(HERE/'run_case.py',('controller_end',),dict(json=json))
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            log = directory/'allocation-events.jsonl'
            log.write_text(''.join(json.dumps(dict(kind='pose',sim=i))+'\n'
                                   for i in range(1000)))
            with patch.object(json,'loads',wraps=json.loads) as loads:
                reason, position = ns['controller_end'](directory,0)
                self.assertIsNone(reason)
                self.assertEqual(loads.call_count,1000)
                for _ in range(10):
                    reason, position = ns['controller_end'](directory,position)
                    self.assertIsNone(reason)
                self.assertEqual(loads.call_count,1000)
                with log.open('a') as stream:
                    stream.write('{"kind":"rl_halt_requested",')
                reason, partial_position = ns['controller_end'](directory,position)
                self.assertEqual((reason,partial_position),(None,position))
                with log.open('a') as stream:
                    stream.write('"reason":"policy_error"}\n')
                reason, position = ns['controller_end'](directory,partial_position)
                self.assertEqual(reason,'policy_error')
                self.assertEqual(loads.call_count,1001)

    def test_boot_propagates_native_failure_and_cleans_xvfb_without_process(self):
        self.check_fake_boot(False)
        self.check_fake_boot(True)

    def check_fake_boot(self,timeout):
        spec = importlib.util.spec_from_file_location('gz01_boot_fixture',HERE/'boot.py')
        boot = importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)
        calls=[]
        class FakeProcess:
            def __init__(self,role):self.role=role;self.waits=0
            def terminate(self):calls.append(self.role+'_terminate')
            def wait(self,timeout=None):
                self.waits+=1
                if self.role=='runner' and timeout==1500 and self.waits==1 and timeout_fixture:
                    raise subprocess.TimeoutExpired('stub',timeout)
                return 1 if self.role=='runner' else 0
            def send_signal(self,sig):calls.append('runner_sigint')
        timeout_fixture=timeout
        def fake_popen(command,**kwargs):
            calls.append(command[0])
            return FakeProcess('xvfb' if command[0]=='Xvfb' else 'runner')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ready=root/'ready.json';ready.write_text('{}')
            admission=dict(case_path=str(root/'case'),outer_wall=1500,cleanup_wall=90)
            with patch.object(boot,'validate_ready',return_value=admission),patch.object(boot.subprocess,'Popen',side_effect=fake_popen),\
                 patch.object(sys,'argv',['boot','--ready',str(ready)]),patch.dict(boot.os.environ,{},clear=False):
                self.assertEqual(boot.main(),1)
            self.assertIn('xvfb_terminate',calls)
            self.assertEqual(json.loads((root/'case.boot-exit.json').read_text())['outer_timeout'],timeout)
            if timeout:self.assertIn('runner_sigint',calls)
            self.assertTrue((root/'case.admission-used.json').exists())


if __name__ == '__main__':
    unittest.main()
