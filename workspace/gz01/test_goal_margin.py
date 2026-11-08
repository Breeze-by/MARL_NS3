"""Pure-mask and controller-construction fixtures: no ROS/model initialization."""
import ast
import copy
import json
from pathlib import Path
import sys
import types
import unittest

HERE=Path(__file__).resolve().parent
PHASE=HERE.parents[1]
sys.path.insert(0,str(PHASE/'workspace/src/multi_robot_exploration'))
from multi_robot_exploration.allocation import Allocator,JointAction
from multi_robot_exploration.joint import candidate_mask,slot_mask,JointTraditionalPolicy,KEEP_SLOT
from system_variants import GOAL_SEPARATION_M


def allocator(observation,separation):
    a=Allocator();a.goal_separation_m=separation
    a.decision_id=observation['decision_id'];a.map_version=observation['map_version']
    for r in observation['robots']:
        a.robots[r['id']].token=r['task_token']
        a.robots[r['id']].state=r['state']
    return a


class GoalMargin(unittest.TestCase):
    def setUp(self):
        path=PHASE/'inputs/historical-goal-margin-50.json'
        self.event=json.loads(path.read_text())

    def test_recorded_near_endpoints_are_masked_and_allocator_agrees(self):
        old=copy.deepcopy(self.event['observed_state_and_candidates'])
        chosen=self.event['choices']
        self.assertTrue(candidate_mask(old,2,chosen[:2])[chosen[2]])
        new=dict(old,goal_separation_m=GOAL_SEPARATION_M['goal-margin-v1'])
        self.assertFalse(candidate_mask(new,2,chosen[:2])[chosen[2]])
        self.assertTrue(candidate_mask(new,2,chosen[:2])[14])
        a=allocator(new,GOAL_SEPARATION_M['goal-margin-v1'])
        _,rejected=a.apply(new,JointAction(new['decision_id'],new['map_version'],tuple(chosen)))
        self.assertEqual(rejected['tb3'],'target_conflict')
        traditional=JointTraditionalPolicy().select(new)
        a=allocator(new,GOAL_SEPARATION_M['goal-margin-v1'])
        _,rejected=a.apply(new,traditional)
        self.assertEqual(rejected,{})
        protected=copy.deepcopy(new);protected['robots'][0]['state']='active'
        self.assertEqual(slot_mask(protected,0).nonzero()[0].tolist(),[KEEP_SLOT])

    def test_boundary_keeps_distant_legal_targets(self):
        observation=dict(candidates=[dict(position=(0.,0.)),dict(position=(1.2,0.)),
            dict(position=(3.,0.))],action_mask=[[True,False,False],[False,True,False],
            [False,False,True]],robots=[dict(id=r) for r in ('tb1','tb2','tb3')],
            goal_separation_m=GOAL_SEPARATION_M['goal-margin-v1'])
        self.assertTrue(candidate_mask(observation,1,(0,))[1])
        observation['candidates'][1]['position']=(1.199,0.)
        self.assertFalse(candidate_mask(observation,1,(0,))[1])

    def test_both_arms_receive_same_explicit_system_parameter(self):
        class Base:
            def __init__(self,*args,**kwargs):
                self.config=dict(step_sim_seconds=5.,episode_decisions=100,
                                 backend=dict(xy_goal_tolerance_m=.25))
                self.allocator=types.SimpleNamespace(goal_separation_m=.70,
                    idle_body_goal_clearance_m=None,seed_connection=None,peer_goal_valid=None)
                self.policy=object();self.records=[]
                self.tf={r:object() for r in ('tb1','tb2','tb3')}
                self.subscriptions_kept=[];self.subscription_calls=[]
            def record(self,row):self.records.append(row)
            def now(self):return 0.
            def create_subscription(self,message_type,topic,callback,qos):
                subscription=types.SimpleNamespace(topic=topic,qos=qos)
                self.subscription_calls.append(subscription)
                return subscription
        tree=ast.parse((HERE/'headquarters.py').read_text())
        nodes=[n for n in tree.body if isinstance(n,ast.Assign)
               and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='EXECUTION']
        nodes.extend(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GZHeadquarters')
        ns=dict(RL04Headquarters=Base,GOAL_SEPARATION_M=GOAL_SEPARATION_M,
                JointTraditionalPolicy=JointTraditionalPolicy,PolicyTrace=lambda policy,*args:policy,
                connect_seed=lambda *args:None,receive_costmap=lambda *args:None,
                OccupancyGrid=object,String=object,QoSProfile=lambda **kwargs:types.SimpleNamespace(**kwargs),
                DurabilityPolicy=types.SimpleNamespace(TRANSIENT_LOCAL='transient_local'))
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(HERE/'headquarters.py'),'exec'),ns)
        for arm in ('rl','traditional'):
            for variant,separation in GOAL_SEPARATION_M.items():
                node=ns['GZHeadquarters'](None,None,Path('/unused'),None,arm,timed=False,
                                         system_variant=variant)
                self.assertEqual(node.allocator.goal_separation_m,separation)
                self.assertEqual(node.records[-1]['system_variant'],variant)
                self.assertEqual(node.config['episode_decisions'],130)
                self.assertEqual(node.allocator.idle_body_goal_clearance_m,
                    {'idle-body-guard-v1':.95,'peer-compact-v1':.55}.get(variant))
                uses_costmap=variant in ('seed-connection-v1','idle-body-guard-v1','peer-compact-v1')
                self.assertEqual([s.topic for s in node.subscriptions_kept],
                    ([f'/{r}/local_costmap/costmap' for r in ('tb1','tb2','tb3')] if uses_costmap else []) + (['/peer_keepout_state'] if variant=='peer-compact-v1' else []))
                self.assertEqual(len(node.subscription_calls),(3 if uses_costmap else 0)+(1 if variant=='peer-compact-v1' else 0))
                self.assertEqual(callable(node.allocator.seed_connection),uses_costmap)
                self.assertEqual(callable(node.allocator.peer_goal_valid),variant=='peer-compact-v1')
                for subscription in node.subscription_calls[:3] if uses_costmap else []:
                    self.assertEqual(subscription.qos.depth,1)
                    self.assertEqual(subscription.qos.durability,'transient_local')


if __name__=='__main__':unittest.main()
