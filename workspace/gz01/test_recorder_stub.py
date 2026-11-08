"""One recorder-only fixture using an explicit Python model stub, not a NN."""
import argparse
import ast
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
import numpy as np

HERE=Path(__file__).resolve().parent


class RecorderFixture(unittest.TestCase):
    evidence = None

    def test_same_single_recording_for_both_arms_without_double_act(self):
        module=ast.parse((HERE/'headquarters.py').read_text())
        policy_class=next(node for node in module.body if isinstance(node,ast.ClassDef) and node.name=='PolicyTrace')
        encode_calls=[]
        def stub_encode(observation,roi):
            encode_calls.append('encode')
            return np.array([1.,2.],dtype=np.float32)
        namespace=dict(np=np,time=time,encode=stub_encode,observed_row=lambda obs:{'stub_observation':True},
            slot_mask=lambda obs,i,prefix:np.ones(17,dtype=bool),choice_to_slot=lambda choice:choice)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[policy_class],type_ignores=[])),
                     str(HERE/'headquarters.py'),'exec'),namespace)
        action=SimpleNamespace(decision_id=7,map_version=3,choices=(0,1,2))
        arrays=dict(inputs=np.array([1.,2.],dtype=np.float32),masks=np.ones((3,17),dtype=bool),
            slots=np.array([0,1,2]),value=.3,logprob=-.2,entropy=.8,action=action)
        class FakeTensor:
            def __init__(self,array):self.array=array
            def detach(self):return self
            def cpu(self):return self
            def numpy(self):return self.array
        class StubModel:
            def __init__(self):self.act_calls=0;self.hook=None
            def register_forward_hook(self,hook):self.hook=hook;return 'stub-hook'
            def act(self,obs,deterministic=False):
                self.act_calls+=1
                if deterministic is not True:raise AssertionError('Lost deterministic call')
                self.hook(self,(),(FakeTensor(np.zeros((1,3,17))),FakeTensor(np.array([.3]))))
                return arrays
        class OldRecorder:
            def __init__(self):self.model=StubModel();self.select_calls=0
            def select(self,obs):
                self.select_calls+=1
                raise AssertionError('Old recording wrapper must not be called')
        class Traditional:
            def __init__(self):self.select_calls=0
            def select(self,obs):self.select_calls+=1;return action
        observation=dict(map=dict(cells=np.array([[0,-1],[100,0]],dtype=np.int8),origin=(0.,0.),resolution=.05))
        results={};saved_keys=[]
        with tempfile.TemporaryDirectory() as temp:
            for arm,policy in [('rl',OldRecorder()),('traditional',Traditional())]:
                events=[]
                local=SimpleNamespace(data=[0,-1,100,0],
                    info=SimpleNamespace(height=2,width=2,resolution=.05,
                        origin=SimpleNamespace(position=SimpleNamespace(x=0.,y=0.))),
                    header=SimpleNamespace(stamp=SimpleNamespace(sec=4,nanosec=0)))
                node=SimpleNamespace(now=lambda:5.,config=dict(task_roi=[0.,0.,1.,1.]),
                                     local_maps={'tb1':local},record=events.append)
                directory=Path(temp)/arm
                trace=namespace['PolicyTrace'](policy,node,directory,arm)
                self.assertIs(trace.select(observation),action)
                files=list(directory.glob('*.npz'));self.assertEqual(len(files),1)
                with np.load(files[0]) as saved:
                    saved_keys.append(set(saved.files))
                    np.testing.assert_array_equal(saved['encoded_inputs'],arrays['inputs'])
                    np.testing.assert_array_equal(saved['conditional_masks'],arrays['masks'])
                    np.testing.assert_array_equal(saved['slots'],arrays['slots'])
                    self.assertEqual(bool(saved['model_output_available']),arm=='rl')
                    self.assertEqual(saved['raw_logits'].shape,(1,3,17) if arm=='rl' else (0,3,17))
                self.assertEqual(len(events),1)
                self.assertEqual(events[0]['input_npz'],str(files[0]))
                self.assertEqual(events[0]['kind'],'rl_real_inference' if arm=='rl' else 'traditional_real_decision')
                results[arm]=dict(stub_act_calls=policy.model.act_calls if arm=='rl' else 0,
                    old_recorder_select_calls=policy.select_calls if arm=='rl' else 0,
                    traditional_select_calls=policy.select_calls if arm=='traditional' else 0,
                    npz_files=len(files),event_kind=events[0]['kind'])
            self.assertEqual(saved_keys[0],saved_keys[1])
        self.assertEqual(results['rl']['stub_act_calls'],1)
        self.assertEqual(results['rl']['old_recorder_select_calls'],0)
        self.assertEqual(results['traditional']['traditional_select_calls'],1)
        self.assertEqual(encode_calls,['encode'])
        RecorderFixture.evidence=dict(status='PASS',fixture='Python model stub only; no actual NN',
            arms=results,same_npz_schema=True,real_nn_forward=0,real_ros_node=0,gazebo_start=0,
            robot_command=0,optimizer_step=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--result',type=Path,required=True);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RecorderFixture))
    args.result.parent.mkdir(parents=True,exist_ok=True)
    with args.result.open('x') as stream:
        json.dump(RecorderFixture.evidence if result.wasSuccessful() else dict(status='FAIL',tests=result.testsRun,
            failures=[text for test,text in result.failures],errors=[text for test,text in result.errors]),stream,indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
