"""High-level training contract; no Gym, learner, synthetic world or ROS reset."""
from .allocation import Allocator
from .evaluation import Evaluator


class AllocationEnvironment:
    """Backend owns physical reset, bounded stepping, Nav2 and safe stopping.

    reset()->{episode_id,world_reset,slam_reset,navigation_cleared,snapshot}
    advance(proposals,max_sim_s)->snapshot
    stop(reason)->bool (actual stop verification, not merely command receipt)
    snapshot={sim,map:{cells,resolution,origin,stamp},robots:{id:{pose,stamp,velocity}},
              events:[{kind:accepted/terminal,robot,token,uuid/status}],reason?,completion?}
    No production Gazebo reset backend is supplied in BASE-02.
    """
    def __init__(self, backend, policy, max_decisions=100, max_sim_s=5., task_roi=None,
                 candidate_mode='legacy', navigation_path_budget_m=None, navigation_goal_tolerance_m=.25):
        self.backend,self.policy=backend,policy
        self.max_decisions,self.max_sim_s=max_decisions,max_sim_s
        self.task_roi=task_roi
        self.candidate_mode=candidate_mode
        self.navigation_path_budget_m=navigation_path_budget_m
        self.navigation_goal_tolerance_m=navigation_goal_tolerance_m
        self.allocator=None
        self.observation=None
        self.done=True

    def _snapshot(self, snapshot):
        a=self.allocator;a.tick(snapshot['sim'])
        m=snapshot['map'];a.update_map(m['cells'],m['resolution'],m['origin'],m['stamp'])
        for robot,data in snapshot['robots'].items():
            a.update_robot(robot,data['pose'],data['stamp'],data['velocity'])
            self.metrics.pose(robot,data['pose'][:2],snapshot['sim'])
        for event in snapshot.get('events',()):
            if event['kind']=='accepted':a.accepted(event['robot'],event['token'],event['uuid'])
            elif event['kind']=='terminal':a.finish(event['robot'],event['token'],event['status'])
        self.observation=a.get_observation()

    def reset(self):
        try:return self._reset()
        except Exception as error:
            self._abort(error)
            raise

    def _abort(self, error):
        self.done=True
        if self.allocator is not None:self.allocator.stop('environment_error')
        self.last_error_info=dict(reason='environment_error',error=f'{type(error).__name__}: {error}',stop_verified=False)
        try:self.last_error_info['stop_verified']=self.backend.stop('environment_error')
        except Exception as stop_error:self.last_error_info['stop_error']=f'{type(stop_error).__name__}: {stop_error}'

    def _reset(self):
        self.done=True
        receipt=self.backend.reset()
        if not all(receipt[k] for k in ('world_reset','slam_reset','navigation_cleared')):
            raise RuntimeError('Incomplete episode reset; do not clear only Python state')
        self.metrics=Evaluator();self.allocator=Allocator(emit=self.metrics.event,local_goal_valid=self.backend.goal_valid,task_roi=self.task_roi,
            candidate_mode=self.candidate_mode, navigation_path_budget_m=self.navigation_path_budget_m,
            navigation_goal_tolerance_m=self.navigation_goal_tolerance_m,
            local_navigation_grid=None if self.candidate_mode=='legacy' else self.backend.navigation_grid)
        self.decisions=0;self.done=False;self.episode_id=receipt['episode_id']
        self._snapshot(receipt['snapshot'])
        return self.observation,dict(episode_id=self.episode_id,reset_verified=True)

    def get_observation(self):return self.observation

    def get_action_mask(self):
        o=self.observation
        return dict(candidates=o['action_mask'],keep=o['keep_mask'],wait=o['wait_mask'])

    def step(self, action=None):
        if self.done:raise RuntimeError('reset is required before stepping a finished episode')
        try:return self._step(action)
        except Exception as error:
            self._abort(error)
            raise

    def _step(self, action):
        before=self.metrics.reward_terms();stamp=self.allocator.now
        action=self.policy.select(self.observation) if action is None else action
        proposals,rejected=self.allocator.apply(self.observation,action)
        snapshot=self.backend.advance(proposals,self.max_sim_s)
        self._snapshot(snapshot);self.decisions+=1
        reason=snapshot.get('reason')
        terminated=reason=='natural_complete'
        if terminated and not snapshot.get('completion'):
            raise ValueError('Natural completion needs an explicit backend completion certificate')
        if snapshot['sim']<=stamp and reason is None:reason='environment_clock_not_advancing'
        if snapshot['sim']-stamp>self.max_sim_s+1e-6:reason='backend_step_budget_exceeded';terminated=False
        if self.decisions>=self.max_decisions and reason is None:reason='decision_budget'
        if all(r.state=='idle' and r.condition=='stalled_wait' for r in self.allocator.robots.values()) and reason is None:reason='stalled_wait'
        truncated=reason is not None and not terminated
        verified=None
        if terminated or truncated:
            self.allocator.stop(reason);verified=self.backend.stop(reason);self.done=True
            if not verified:
                reason='stop_not_verified';terminated=False;truncated=True
                self.allocator.stop(reason)
        after=self.metrics.reward_terms()
        reward={name:after[name]-value for name,value in before.items()}
        info=dict(episode_id=self.episode_id,reason=reason,rejected_actions=rejected,
                  stop_verified=verified,metrics=self.metrics.summary(),completion=snapshot.get('completion'))
        return self.observation,reward,terminated,truncated,info
