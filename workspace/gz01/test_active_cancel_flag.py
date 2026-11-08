"""Targeted ready-flag parser fixture; no Node/model/process initialization."""
import argparse
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent


class ActiveCancelFlagFixture(unittest.TestCase):
    def test_only_explicit_autonomous_bool_enables_original_trigger(self):
        source=(HERE/'boot.py').read_text()
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='validate_ready')
        # Execute the actual authorization/mode/flag parser prefix without
        # importing or exercising unrelated model/source-hash validation.
        prefix=[]
        for statement in node.body:
            if "ready['checkpoint_sha256']" in (ast.get_source_segment(source,statement) or ''):
                break
            prefix.append(statement)
        node.body=prefix+[ast.Return(value=ast.Name(id='active_cancel_check',ctx=ast.Load()))]
        node.name='parse_flag'
        namespace=dict(Path=Path,json=json)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(HERE/'boot.py'),'exec'),namespace)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'ready.json'
            def parse(mode='autonomous',**extra):
                path.write_text(json.dumps(dict(authorized_gz01_execution=True,mode=mode,arm='rl',**extra)))
                return namespace['parse_flag'](path)
            self.assertIs(parse(),False)
            self.assertIs(parse(active_cancel_check=True),True)
            self.assertIs(parse(mode='stationary_only',active_cancel_check=False),False)
            with self.assertRaisesRegex(ValueError,'autonomous mode'):
                parse(mode='stationary_only',active_cancel_check=True)
            for invalid in (1,'true',None):
                with self.assertRaisesRegex(ValueError,'JSON bool'):
                    parse(active_cancel_check=invalid)
        run=ast.parse((HERE/'run_case.py').read_text())
        bindings=[n for n in ast.walk(run) if isinstance(n,ast.keyword) and n.arg=='active_cancel_check']
        self.assertEqual(len(bindings),1)
        self.assertEqual(ast.unparse(bindings[0].value),"ready['active_cancel_check']")
        self.assertIn('if args.active_cancel_check and observer.sim-start_sim >= 30.0 and all(',
                      (HERE/'run_case.py').read_text())
        gate=next(node.value for node in ast.walk(run) if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Subscript) and ast.unparse(target)=="result['run_integrity']" for target in node.targets))
        expression=compile(ast.fix_missing_locations(ast.Expression(body=gate)),'<actual-run-integrity-gate>','eval')
        base=dict(preflight=True,error=None,observed_stop=True,lifecycle_pause_healthy=True,
                  final_request_ownership=dict(closed=True),active_cancel_pass=False)
        namespace=dict(result=base,observer=type('ObserverStub',(),dict(hazard=None))())
        namespace['args']=type('ArgsStub',(),dict(active_cancel_check=True))()
        self.assertIs(eval(expression,namespace),False)
        namespace['args'].active_cancel_check=False
        self.assertIs(eval(expression,namespace),True)

    def test_recorded_controller_cancellation_and_missing_evidence_negatives(self):
        case=HERE.parents[1]/'runs/safety-rooms-01'
        result=json.loads((case/'result.json').read_text())
        event=next(json.loads(line) for line in (case/'events.jsonl').read_text().splitlines()
                   if json.loads(line)['kind']=='active_cancel_trigger')
        result['cancel_trigger_positions']=event['positions']
        function=next(n for n in ast.parse((HERE/'run_case.py').read_text()).body
                      if isinstance(n,ast.FunctionDef) and n.name=='active_cancel_complete')
        namespace=dict(ROBOTS=('tb1','tb2','tb3'))
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(HERE/'run_case.py'),'exec'),namespace)
        check=namespace['active_cancel_complete']
        self.assertTrue(check(result))
        for condition in ('missing_terminal','wrong_uuid','unowned_uuid','not_moving',
                          'no_stop','authority_alive','unclosed','hazard'):
            changed=copy.deepcopy(result)
            uuid=changed['cancel_trigger']['tb1'][0]
            if condition=='missing_terminal':
                changed['action_statuses']['tb1']=[p for p in changed['action_statuses']['tb1'] if p!=[uuid,5]]
            elif condition=='wrong_uuid':changed['cancel_trigger']['tb1']=['unrelated']
            elif condition=='unowned_uuid':changed['final_request_ownership']['owned_goals']['tb1']=[]
            elif condition=='not_moving':changed['cancel_trigger_positions']['tb1'][3]=0.
            elif condition=='no_stop':changed['observed_stop']=False
            elif condition=='authority_alive':changed['final_request_ownership']['authority_stopped']=False
            elif condition=='unclosed':changed['final_request_ownership']['closed']=False
            elif condition=='hazard':changed['hazard']='fixture'
            with self.subTest(condition=condition):self.assertFalse(check(changed))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--result',type=Path,required=True);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ActiveCancelFlagFixture))
    payload=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        active_cancel_default=False,explicit_autonomous_true=True,stationary_true_rejected=True,
        non_bool_rejected=True,active_cancel_failed_native_gate=False,normal_mode_ignores_cancel_success=True,
        original_trigger_binding='ready.active_cancel_check',
        actual_source_execution_admitted=False,root_ready_required=True,ros_node=0,nn_forward=0,
        gazebo_start=0,process_spawn=0,robot_command=0)
    args.result.parent.mkdir(parents=True,exist_ok=True)
    with args.result.open('x') as stream:json.dump(payload,stream,indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
