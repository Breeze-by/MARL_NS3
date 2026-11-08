"""Deterministic contract tests; no ROS nodes, simulator or learner runs."""
import ast
from concurrent.futures import Future
import importlib.util
import math
from pathlib import Path
import sys
import threading
import json
import tempfile
from types import SimpleNamespace as NS
import unittest
import numpy as np

ROOT=Path('/project')
sys.path.insert(0,str(ROOT/'workspace/src/multi_robot_exploration'))
from multi_robot_exploration import frontier
from multi_robot_exploration.allocation import Allocator,JointAction,KEEP,WAIT,TraditionalPolicy,TestPolicy,RLPolicy
from multi_robot_exploration.control import HeadquartersControl
from multi_robot_exploration.environment import AllocationEnvironment
from multi_robot_exploration.evaluation import Evaluator,summarize_log
from geometry_msgs.msg import Point,Quaternion
from rclpy.time import Time

spec=importlib.util.spec_from_file_location('frozen_base01',ROOT/'evidence/baseline_control.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)


def grid():
    data=np.full((64,64),-1,dtype=int);data[8:56,8:56]=0
    return data


def allocator(valid=lambda *args:True):
    a=Allocator(local_goal_valid=valid);a.update_map(grid(),.1,(0.,0.),0.)
    for r in a.robots:a.update_robot(r,(3.25,3.25,0.),0.,(0.,0.,0.))
    a.tick(1.)
    return a


class FixtureBackend:
    """Only an interface fixture, with no simulated physics or exploration claim."""
    def __init__(self):self.sim=0.;self.reason=None;self.reset_ok=True;self.stopped=[];self.stop_ok=True
    def goal_valid(self,*args):return True
    def snapshot(self,events=()):
        return dict(sim=self.sim,map=dict(cells=grid(),resolution=.1,origin=(0.,0.),stamp=self.sim),
            robots={r:dict(pose=(3.25,3.25,0.),stamp=self.sim,velocity=(0.,0.,0.)) for r in ('tb1','tb2','tb3')},
            events=events,reason=self.reason,completion={'criterion':'fixture_explicit_completion'} if self.reason=='natural_complete' else None,
            truth_map='EVALUATION-ONLY SENTINEL; must not enter policy state')
    def reset(self):
        self.sim=0.
        return dict(episode_id='fixture-episode',world_reset=self.reset_ok,slam_reset=self.reset_ok,
                    navigation_cleared=self.reset_ok,snapshot=self.snapshot())
    def advance(self,proposals,max_sim_s):
        self.sim+=1.
        events=[]
        for r,(_,token) in proposals.items():
            events += [dict(kind='accepted',robot=r,token=token,uuid=f'{r}-{token}'),
                       dict(kind='terminal',robot=r,token=token,status='succeeded')]
        return self.snapshot(events)
    def stop(self,reason):self.stopped.append(reason);return self.stop_ok


class ContractTests(unittest.TestCase):
    def test_01_frontier_lift_is_ast_identical(self):
        def functions(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
        old=functions((ROOT/'evidence/baseline_control.py').read_text());new=functions(Path(frontier.__file__).read_text())
        for name in ('costmap','frontierB','dfs','assign_groups','fGroups','calculate_centroid','reachable_free_cells','findClosestGroup','exploration'):
            self.assertEqual(old[name],new[name],name)

    def test_02_traditional_matches_frozen_inputs_history_and_last_target(self):
        compared=0
        for seed in range(8):
            data=grid();rng=np.random.default_rng(seed)
            for _ in range(seed%4):
                row,col=rng.integers(18,46,size=2);data[row,col]=100
            for scenario in ('plain','visited','failed','reserved','last_target'):
                a=allocator();a.update_map(data,.1,(0.,0.),1.)
                obs=a.get_observation(trigger='tb1');proposal=TraditionalPolicy().select(obs).choices[0]
                target=None if proposal<0 else obs['candidates'][proposal]['position']
                if target is not None:
                    if scenario=='visited':a.visited=[target]
                    elif scenario=='failed':a.failed['tb1']=[target]
                    elif scenario=='reserved':a.robots['tb2'].target=target;a.robots['tb2'].state='active'
                    elif scenario=='last_target':a.robots['tb1'].last_success=target
                original.VISITED[:]=a.visited;original.FAILED.clear();original.FAILED.update(a.failed)
                original.ASSIGNED.clear();original.ASSIGNED.update({r:q.target for r,q in a.robots.items() if q.target is not None})
                old=original.exploration(data,64,64,.1,32,32,0.,0.,'tb1',a.robots['tb1'].last_success)
                obs=a.get_observation(trigger='tb1');choice=TraditionalPolicy().select(obs).choices[0]
                new=None if choice<0 else obs['candidates'][choice]['position']
                self.assertEqual(old,new,(seed,scenario));compared+=1
        self.assertEqual(compared,40)

    def test_03_equal_score_order_and_post_selection_veto(self):
        obs=dict(decision_id=1,map_version=1,trigger=None,robots=[dict(id='tb1',state='idle',last_success=None)],
            candidates=[dict(robot='tb1',traditional_eligible=True,traditional_score=2.,position=(1.,1.)),
                        dict(robot='tb1',traditional_eligible=True,traditional_score=2.,position=(3.,3.))])
        self.assertEqual(TraditionalPolicy().select(obs).choices,(0,))
        obs['robots'][0]['last_success']=(1.,1.)
        self.assertEqual(TraditionalPolicy().select(obs).choices,(WAIT,))
        matrix=np.zeros((9,9));groups=[(1,[(2,3),(2,4),(2,5)]),(2,[(6,3),(6,4),(6,5)])]
        original.VISITED.clear();original.ASSIGNED.clear();original.FAILED.clear()
        self.assertEqual(original.findClosestGroup(matrix,groups,(4,4),1.,0.,0.,'tb1'),(4.5,2.5))

    def test_04_observation_map_sources_and_three_robots(self):
        a=allocator();o=a.get_observation()
        self.assertEqual(tuple(r['id'] for r in o['robots']),('tb1','tb2','tb3'))
        self.assertTrue(all(len(r['pose'])==3 for r in o['robots']))
        self.assertEqual(o['map']['source'],'/merge_map');self.assertEqual(o['map_version'],1)
        self.assertTrue(o['candidates']);self.assertTrue(all(c['reachable'] and c['path_cost_estimate_m']>=0 for c in o['candidates']))
        self.assertTrue(all(c['information_gain_proxy_m2']>0 for c in o['candidates']))
        with self.assertRaises(TypeError):o['candidates'][0]['position']=(999.,999.)
        with self.assertRaises(ValueError):o['map']['cells'].flags.writeable=True

    def test_05_modes_share_state_and_validation(self):
        for mode in ('traditional','test','rl'):
            a=allocator();o=a.get_observation(trigger='tb1')
            policy={'traditional':TraditionalPolicy(),'test':TestPolicy(),'rl':RLPolicy(lambda x:TraditionalPolicy().select(x).choices)}[mode]
            proposals,rejected=a.apply(o,policy.select(o))
            self.assertIn('tb1',proposals);self.assertFalse(rejected)
            self.assertEqual(a.map_version,1)
        with self.assertRaisesRegex(RuntimeError,'not attached'):RLPolicy().select(o)

    def test_06_numpy_indices_allowed_bool_float_rejected(self):
        a=allocator();o=a.get_observation(trigger='tb1')
        policy=RLPolicy(lambda x:np.asarray(TraditionalPolicy().select(x).choices,dtype=np.int64))
        self.assertIn('tb1',a.apply(o,policy.select(o))[0])
        for value in (True,.0,1.2):
            a=allocator();o=a.get_observation()
            with self.assertRaises(ValueError):a.apply(o,JointAction(o['decision_id'],o['map_version'],(value,WAIT,WAIT)))

    def test_07_stale_snapshot_and_task_ownership_rejected(self):
        a=allocator();o=a.get_observation();action=TraditionalPolicy().select(o)
        a.get_observation()
        with self.assertRaises(ValueError):a.apply(o,action)
        o=a.get_observation();action=TraditionalPolicy().select(o);a.update_map(np.zeros((64,64)),.1,(0.,0.),2.)
        with self.assertRaises(ValueError):a.apply(o,action)
        a=allocator();o=a.get_observation();action=TraditionalPolicy().select(o);a.robots['tb1'].state='pending'
        with self.assertRaises(ValueError):a.apply(o,action)

    def test_08_local_invalid_and_unknown_data_never_dispatch(self):
        for validity in (False,None):
            a=allocator(lambda *args:validity);o=a.get_observation(trigger='tb1');action=TraditionalPolicy().select(o)
            proposals,rejected=a.apply(o,action)
            self.assertFalse(proposals);self.assertTrue(rejected)
            self.assertEqual(bool(a.failed['tb1']),validity is False)
        a=allocator();o=a.get_observation(trigger='tb1')
        proposals,rejected=a.apply(o,JointAction(o['decision_id'],o['map_version'],(999,WAIT,WAIT)))
        self.assertFalse(proposals);self.assertTrue(rejected)

    def test_09_active_keep_duplicate_protection_and_redispatch(self):
        a=allocator();o=a.get_observation(trigger='tb1');target,token=a.apply(o,TraditionalPolicy().select(o))[0]['tb1']
        self.assertTrue(a.accepted('tb1',token,'uuid-1'))
        o=a.get_observation(trigger='tb1');self.assertTrue(o['keep_mask'][0])
        self.assertFalse(a.apply(o,JointAction(o['decision_id'],o['map_version'],(KEEP,WAIT,WAIT)))[0])
        o=a.get_observation(trigger='tb1');self.assertIn('tb1',a.apply(o,JointAction(o['decision_id'],o['map_version'],(0,WAIT,WAIT)))[1])
        self.assertTrue(a.finish('tb1',token,'succeeded'));self.assertEqual(a.robots['tb1'].last_success,target)
        # A new valid allocation may be made after terminal, then old result cannot release it.
        expanded=np.full((64,64),-1);expanded[2:62,2:62]=0
        a.update_map(expanded,.1,(0.,0.),2.)
        o=a.get_observation(trigger='tb1');newtoken=a.apply(o,TraditionalPolicy().select(o))[0]['tb1'][1]
        self.assertFalse(a.finish('tb1',token,'aborted'));self.assertEqual(a.robots['tb1'].token,newtoken)

    def test_10_conflict_and_same_robot_local_masks(self):
        a=allocator();o=a.get_observation();self.assertTrue(o['candidate_conflicts'])
        proposals,rejected=a.apply(o,TraditionalPolicy().select(o))
        self.assertEqual(len(proposals),1);self.assertTrue(all(v=='target_conflict' for v in rejected.values()))

    def test_11_no_candidates_stall_timeout_and_no_false_completion(self):
        a=allocator();a.update_map(np.full((64,64),100),.1,(0.,0.),2.)
        for _ in range(5):
            o=a.get_observation(trigger='tb1');self.assertFalse(any(o['action_mask'][0]));a.apply(o,TraditionalPolicy().select(o))
        self.assertEqual(a.robots['tb1'].condition,'stalled_wait')
        a=allocator();o=a.get_observation(trigger='tb1');_,token=a.apply(o,TraditionalPolicy().select(o))[0]['tb1']
        a.accepted('tb1',token,'uuid');a.task_timeout_s=2.;a.tick(4.)
        self.assertTrue(a.robots['tb1'].cancel_requested);self.assertEqual(a.robots['tb1'].state,'active')

    def test_12_hard_stop_cannot_be_bypassed(self):
        a=allocator();o=a.get_observation(trigger='tb1');_,token=a.apply(o,TraditionalPolicy().select(o))[0]['tb1']
        a.stop('safety_stop')
        self.assertFalse(a.accepted('tb1',token,'late-uuid'))
        with self.assertRaises(RuntimeError):a.apply(o,TraditionalPolicy().select(o))

    def test_13_real_nav2_goal_conversion_uses_same_adapter(self):
        for policy in (TraditionalPolicy(),TestPolicy(),RLPolicy(lambda o:TraditionalPolicy().select(o).choices)):
            a=allocator();o=a.get_observation(trigger='tb1');target,token=a.apply(o,policy.select(o))[0]['tb1']
            sent=[];future=Future()
            owner=NS(lock=threading.RLock(),allocator=a,
                robot_nav_clients={'tb1':NS(wait_for_server=lambda **kw:True,send_goal_async=lambda goal,**kw:sent.append(goal) or future)},
                local_point=lambda r,t:(Point(x=t[0]-5.,y=t[1]-4.),Quaternion(w=1.)),
                nav_goal_in_local_map=lambda *args:True,get_clock=lambda:NS(now=lambda:Time(seconds=1.)),
                goal_response_callback=lambda *args:None,feedback_callback=lambda *args:None)
            HeadquartersControl.send_goal(owner,'tb1',target,token)
            self.assertEqual(len(sent),1);self.assertEqual(sent[0].pose.header.frame_id,'map')
            self.assertEqual(sent[0].pose.pose.position.x,target[0]-5.)

    def test_14_reset_is_not_python_counter_reset(self):
        b=FixtureBackend();env=AllocationEnvironment(b,TestPolicy());b.reset_ok=False
        with self.assertRaisesRegex(RuntimeError,'Incomplete'):env.reset()
        self.assertTrue(env.done);self.assertIsNone(env.allocator)

    def test_15_environment_step_reward_budget_and_stop(self):
        b=FixtureBackend();env=AllocationEnvironment(b,TestPolicy(),max_decisions=1)
        obs,info=env.reset();self.assertTrue(info['reset_verified']);self.assertNotIn('truth_map',obs)
        obs,reward,terminated,truncated,info=env.step()
        self.assertFalse(terminated);self.assertTrue(truncated);self.assertEqual(info['reason'],'decision_budget')
        self.assertEqual(reward['elapsed_sim_s'],1.);self.assertTrue(info['stop_verified'])
        self.assertIn('candidates',env.get_action_mask())
        with self.assertRaises(RuntimeError):env.step()

    def test_16_end_reasons_and_unverified_stop(self):
        for reason in ('natural_complete','navigation_failure','environment_error','safety_stop','manual_abort'):
            b=FixtureBackend();env=AllocationEnvironment(b,TestPolicy());env.reset();b.reason=reason
            _,_,terminated,truncated,info=env.step()
            self.assertEqual(terminated,reason=='natural_complete');self.assertEqual(truncated,reason!='natural_complete')
            self.assertEqual(info['reason'],reason)
        b=FixtureBackend();env=AllocationEnvironment(b,TestPolicy(),max_decisions=1);env.reset();b.stop_ok=False
        _,_,terminated,truncated,info=env.step();self.assertFalse(terminated);self.assertTrue(truncated)
        self.assertEqual(info['reason'],'stop_not_verified')
        self.assertEqual(info['metrics']['stop_reason'],'stop_not_verified')

    def test_17_evaluation_truth_separate_and_observable_metrics(self):
        a=allocator();o=a.get_observation();m=Evaluator()
        m.event(dict(kind='map_changed',sim=1.,known_area_m2=1.));m.event(dict(kind='map_changed',sim=2.,known_area_m2=2.))
        m.pose('tb1',(0.,0.),1.);m.pose('tb1',(3.,4.),2.)
        self.assertEqual(m.summary()['odometry_distance_m']['tb1'],5.)
        self.assertIsNone(m.summary()['reference_coverage'])
        m.reference_coverage([[True,False]],[[True,True]],2.)
        self.assertEqual(m.summary()['reference_coverage'],.5)
        self.assertEqual(m.reward_terms()['new_shared_known_area_m2'],1.)
        self.assertNotIn('reference_coverage',o);self.assertNotIn('truth_map',o)

    def test_18_ros_guard_and_no_low_level_control_or_truth(self):
        text=(ROOT/'workspace/src/multi_robot_exploration/multi_robot_exploration/control.py').read_text()
        self.assertIn("if mode != 'traditional'",text)
        tree=ast.parse(text)
        self.assertFalse(any(isinstance(n,ast.Attribute) and n.attr=='create_publisher' for n in ast.walk(tree)))
        self.assertNotIn('gazebo_msgs',text);self.assertNotIn('ModelStates',text)

    def test_19_external_errors_stop_then_expose_original_failure(self):
        for where in ('policy','advance','reset'):
            b=FixtureBackend();env=AllocationEnvironment(b,TestPolicy());env.reset()
            def fail(*args):raise RuntimeError('injected '+where)
            if where=='policy':env.policy=NS(select=fail)
            elif where=='advance':b.advance=fail
            else:b.reset=fail
            with self.assertRaisesRegex(RuntimeError,'injected '+where):
                if where=='reset':env.reset()
                else:env.step()
            self.assertEqual(b.stopped[-1],'environment_error');self.assertTrue(env.done)
            self.assertTrue(env.last_error_info['stop_verified'])

    def test_20_metrics_info_is_a_snapshot(self):
        m=Evaluator();m.pose('tb1',(0.,0.),0.)
        saved=m.summary();m.pose('tb1',(1.,0.),1.)
        m.event(dict(kind='goal_terminal',sim=1.,robot='tb1',status='aborted'))
        self.assertEqual(saved['odometry_distance_m']['tb1'],0.)
        self.assertEqual(saved['statuses']['tb1'],{})

    def test_21_transport_cancels_late_handle_and_never_dispatches_after_stop(self):
        a=allocator();o=a.get_observation(trigger='tb1');target,token=a.apply(o,TraditionalPolicy().select(o))[0]['tb1']
        a.stop('safety_stop');sent=[];canceled=[];result=Future()
        owner=NS(lock=threading.RLock(),allocator=a,goal_handles={},
            robot_nav_clients={'tb1':NS(wait_for_server=lambda **kw:True,send_goal_async=lambda *args,**kw:sent.append(args))},
            goal_result_callback=lambda *args:None)
        HeadquartersControl.send_goal(owner,'tb1',target,token);self.assertFalse(sent)
        handle=NS(accepted=True,goal_id=NS(uuid=[1]*16),cancel_goal_async=lambda:canceled.append(True),get_result_async=lambda:result)
        future=Future();future.set_result(handle)
        HeadquartersControl.goal_response_callback(owner,'tb1',token,future)
        self.assertTrue(canceled);self.assertFalse(owner.goal_handles)

    def test_22_evaluation_event_window_matches_trajectory_window(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'events.jsonl'
            events=[dict(kind='goal_reserved',sim=s,robot='tb1',target=(s,0.)) for s in (1.,10.,20.)]
            path.write_text(''.join(json.dumps(e)+'\n' for e in events))
            result=summarize_log(path,start_sim=5.,end_sim=15.)
            self.assertEqual(result['assignments']['tb1'],1)
            self.assertEqual(result['evaluation_interval_sim_s'],[5.,15.])

    def test_23_observer_terminal_does_not_reverse_metric_time(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'events.jsonl';observer=Path(temp)/'observer.jsonl'
            path.write_text(''.join(json.dumps(dict(kind='goal_reserved',sim=s,robot='tb1',target=(s,0.)))+'\n' for s in (1.,10.)))
            observer.write_text(json.dumps(dict(kind='action_status',sim=5.,robot='tb1',goal='other-uuid',status=5))+'\n')
            result=summarize_log(path,observer_events=observer)
            self.assertEqual(result['reward_components']['elapsed_sim_s'],9.)
            self.assertEqual(result['cancellations'],1)


if __name__=='__main__':unittest.main(verbosity=2)
