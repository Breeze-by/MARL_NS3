"""Shared observable metrics. Reference coverage is an evaluator-only input."""
import json
import math
import csv
from copy import deepcopy
from pathlib import Path
import numpy as np


class Evaluator:
    def __init__(self, robots=('tb1','tb2','tb3')):
        self.distance={r:0. for r in robots}
        self.assignments={r:0 for r in robots}
        self.feedback_count={r:0 for r in robots}
        self.previous={}
        self.last_targets={}
        self.statuses={r:{} for r in robots}
        self.known_area=None
        self.new_known_area=0.
        self.duplicate_assignments=0
        self.conflicts=0
        self.cancels=0
        self.switches=0
        self.first_sim=None
        self.last_sim=None
        self.reason=None
        self.coverage=None
        self.coverage_times={}

    def pose(self, robot, position, stamp):
        if robot in self.previous:self.distance[robot]+=math.dist(position,self.previous[robot])
        self.previous[robot]=position
        self._time(stamp)

    def _time(self, stamp):
        self.first_sim=stamp if self.first_sim is None else min(self.first_sim,stamp)
        self.last_sim=stamp if self.last_sim is None else max(self.last_sim,stamp)

    def feedback(self, robot, remaining):
        self.feedback_count[robot]+=1

    def event(self, event):
        self._time(event['sim'])
        kind=event['kind'];robot=event.get('robot')
        if kind=='pose':self.pose(robot,event['position'],event['sim'])
        elif kind=='feedback':self.feedback(robot,event['remaining'])
        elif kind=='map_changed':
            area=event['known_area_m2']
            if self.known_area is not None:self.new_known_area+=max(0.,area-self.known_area)
            self.known_area=area
        elif kind=='goal_reserved':
            self.assignments[robot]+=1
            if robot in self.last_targets and math.dist(event['target'],self.last_targets[robot])<.2:
                self.duplicate_assignments+=1
            self.last_targets[robot]=tuple(event['target'])
        elif kind=='goal_terminal':
            status=event['status']; counts=self.statuses[robot];counts[status]=counts.get(status,0)+1
            self.cancels+=status=='canceled'
        elif kind=='action_rejected' and event['reason']=='target_conflict':self.conflicts+=1
        elif kind=='allocator_halted':self.reason=event['reason']

    def reference_coverage(self, observed, reference_free, sim, thresholds=(.9,.95)):
        """Evaluator-only aligned boolean masks; never attached to observations."""
        observed=np.asarray(observed,dtype=bool); reference_free=np.asarray(reference_free,dtype=bool)
        if observed.shape!=reference_free.shape or not np.any(reference_free):
            raise ValueError('Coverage requires aligned masks and a nonempty fixed reference region')
        self.coverage=float(np.count_nonzero(observed & reference_free)/np.count_nonzero(reference_free))
        for threshold in thresholds:
            if self.coverage>=threshold:self.coverage_times.setdefault(str(threshold),sim-self.first_sim)

    def reward_terms(self):
        return dict(new_shared_known_area_m2=self.new_known_area,
                    elapsed_sim_s=0. if self.first_sim is None else self.last_sim-self.first_sim,
                    navigation_distance_m=sum(self.distance.values()),
                    duplicate_assignment_count=self.duplicate_assignments,
                    target_switch_count=self.switches,target_conflict_count=self.conflicts)

    def summary(self):
        successes=sum(v.get('succeeded',0) for v in self.statuses.values())
        nav_failures=sum(v.get('aborted',0)+v.get('rejected',0) for v in self.statuses.values())
        denominator=successes+nav_failures
        return deepcopy(dict(odometry_distance_m=self.distance,participating_robots=[r for r,d in self.distance.items() if d>.1],
            assignments=self.assignments,feedback_counts=self.feedback_count,statuses=self.statuses,
            nav_success_rate=None if not denominator else successes/denominator,
            nav_failure_rate=None if not denominator else nav_failures/denominator,
            cancellations=self.cancels,target_switches=self.switches,duplicate_assignments=self.duplicate_assignments,
            target_conflicts=self.conflicts,shared_known_area_m2=self.known_area,
            reference_coverage=self.coverage,coverage_threshold_sim_s=self.coverage_times,
            stop_reason=self.reason,reward_components=self.reward_terms(),
            repeated_exploration_area_m2=None,
            unavailable_reason='Reference coverage needs independent fixed masks; repeated sensing area not identifiable from merged counts.'))


def summarize_log(path, trajectories=None, start_sim=-math.inf, end_sim=math.inf, observer_events=None):
    metrics=Evaluator()
    terminals=set()
    for line in Path(path).read_text().splitlines():
        event=json.loads(line)
        if not start_sim<=event['sim']<=end_sim:continue
        metrics.event(event)
        if event['kind']=='goal_terminal' and event.get('uuid'):terminals.add((event['robot'],event['uuid']))
    case_end_reason=None
    if observer_events is not None:
        for line in Path(observer_events).read_text().splitlines():
            event=json.loads(line)
            if event['kind']=='finished':
                case_end_reason=event['end_reason'] if event['error'] is None else event['error']
            if event['sim'] is None or not start_sim<=event['sim']<=end_sim:continue
            if event['kind']=='action_status' and event['status'] in (4,5,6):
                key=(event['robot'],event['goal'])
                if key not in terminals:
                    metrics.event(dict(kind='goal_terminal',sim=event['sim'],robot=event['robot'],
                        status={4:'succeeded',5:'canceled',6:'aborted'}[event['status']]))
                    terminals.add(key)
            elif event['kind']=='finished':
                metrics.reason=event['end_reason'] if event['error'] is None else event['error']
    result=metrics.summary()
    result['evaluation_interval_sim_s']=[start_sim if math.isfinite(start_sim) else None,end_sim if math.isfinite(end_sim) else None]
    result['case_end_reason']=case_end_reason
    if trajectories is not None:
        previous={};distance={r:0. for r in metrics.distance}
        for row in csv.DictReader(Path(trajectories).open()):
            if not start_sim<=float(row['sim_s'])<=end_sim:continue
            r=row['robot'];p=(float(row['x']),float(row['y']))
            if r in previous:distance[r]+=math.dist(p,previous[r])
            previous[r]=p
        result['evaluation_only_gazebo_distance_m']=distance
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('log');parser.add_argument('--trajectories')
    parser.add_argument('--observer-events')
    parser.add_argument('--start-sim',type=float,default=-math.inf)
    parser.add_argument('--end-sim',type=float,default=math.inf)
    args=parser.parse_args()
    print(json.dumps(summarize_log(args.log,args.trajectories,args.start_sim,args.end_sim,args.observer_events),indent=2))
