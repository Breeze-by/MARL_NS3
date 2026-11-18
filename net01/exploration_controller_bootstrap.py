"""Explicit new candidate behavior over the existing traced/graceful HQ owner."""
import os
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def main():
    from execution_profile import load_profile
    from candidate_clearance import VERSION, candidate_headquarters
    from shared_navigation_map import (
        ACTIVE_ROUTE_VERSION, VERSION as IMMEDIATE_SHARED_MAP, selected as shared_map_selected, goal_map_evidence,
        install_hq as install_shared_navigation_map)
    profile = load_profile(os.environ.get('NET01_EXECUTION_PROFILE'))
    if profile is None or profile.get('candidate_clearance', {}).get('id') != VERSION:
        raise ValueError('Exploration bootstrap requires the explicit new candidate baseline')
    for path in (REPO/'workspace/gz01', REPO/'workspace/rl04', REPO/'workspace/rl02',
                 REPO/'workspace/rl01', REPO/'workspace/src/multi_robot_exploration'):
        sys.path.insert(0, str(path))
    import headquarters as frozen
    import consumer_controller_bootstrap
    freshness = None
    if profile.get('source_freshness') is not None:
        from ros_delay_runtime import install_source_freshness
        freshness = install_source_freshness(profile, 'HQ')
    navigation_progress = os.environ.get('NET01_NAVIGATION_PROGRESS_REVISION')
    if navigation_progress:
        from nav_progress_guard import load_contract, install_nav_progress_guard
        profile = dict(profile, nav_progress_guard=load_contract(navigation_progress))
    navigation_planner = os.environ.get('NET01_NAVIGATION_PLANNER_REVISION')
    if navigation_planner:
        contract=json.loads((HERE/'config/NAVIGATION_SMAC2D_FLOOR_V4.json').read_text())
        if navigation_planner != contract['revision']:
            raise ValueError('Unknown planner revision')
        profile=dict(profile,nav2_goal_guard=contract['goal_guard'])
    shared_navigation_map = shared_map_selected(os.environ)
    if shared_navigation_map:
        profile=dict(profile, shared_navigation_map=True)
    navigation_intent = os.environ.get('NET01_FRONTIER_INTENT_REVISION')
    if navigation_intent:
        from shared_frontier_reservation import load_contract as load_intent_contract, install_shared_frontier_reservation
        intent_contract = load_intent_contract(navigation_intent)
    navigation_pairs = os.environ.get('NET01_MIXED_FRONTIER_PAIR_REVISION')
    if navigation_pairs:
        from mixed_frontier_pairs import load_contract as load_pair_contract, install_mixed_frontier_pairs
        pair_contract = load_pair_contract(navigation_pairs)
    navigation_budget = os.environ.get('NET01_NOMINAL_GOAL_BUDGET_REVISION')
    if navigation_budget:
        from nominal_goal_budget import load_contract as load_budget_contract, install_nominal_goal_budget
        budget_contract = load_budget_contract(navigation_budget)
    representative_diagnostic=os.environ.get('NET01_REPRESENTATIVE_DIAGNOSTIC_REVISION')
    if representative_diagnostic:
        from representative_diagnostic import load_contract as load_diagnostic_contract, install_representative_diagnostic
        diagnostic_contract=load_diagnostic_contract(representative_diagnostic)
    frontier_representative=os.environ.get('NET01_FRONTIER_REPRESENTATIVE_REVISION')
    if frontier_representative:
        from frontier_representative import load_contract as load_frontier_contract, install_frontier_representative
        frontier_contract=load_frontier_contract(frontier_representative)
    original = frozen.GZHeadquarters
    configured = original
    if freshness is not None or navigation_progress or navigation_planner or navigation_intent or navigation_pairs or navigation_budget or representative_diagnostic or frontier_representative:
        class ConfiguredHeadquarters(original):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if freshness is not None:
                    self.record(dict(kind='ros_delay_source_freshness', sim=self.now(), applied=freshness))
                if navigation_planner:
                    self.record(dict(kind='navigation_planner_goal_guard_applied',sim=self.now(),
                        pid=os.getpid(),revision=navigation_planner,contract=contract))
                if navigation_progress:
                    install_nav_progress_guard(self, profile)
                    self.record(dict(kind='navigation_progress_guard_applied', sim=self.now(),
                        pid=os.getpid(), revision=navigation_progress,
                        contract=self._nav_progress_guard.contract))
                if navigation_intent:
                    install_shared_frontier_reservation(self, intent_contract)
                    self.record(dict(kind='shared_frontier_reservation_applied', sim=self.now(),
                        pid=os.getpid(), revision=navigation_intent, contract=intent_contract,
                        actual_candidate_mode=self.allocator.candidate_mode))

                if navigation_pairs:
                    install_mixed_frontier_pairs(self, pair_contract)
                    self.record(dict(kind='mixed_frontier_pairs_applied', sim=self.now(),
                        pid=os.getpid(), revision=navigation_pairs, contract=pair_contract,
                        actual_candidate_mode=self.allocator.candidate_mode))

                if navigation_budget:
                    install_nominal_goal_budget(self, budget_contract, profile)
                    self.record(dict(kind='nominal_goal_budget_applied', sim=self.now(),
                        pid=os.getpid(), revision=navigation_budget, contract=budget_contract,
                        actual_candidate_mode=self.allocator.candidate_mode))

                if representative_diagnostic:
                    install_representative_diagnostic(self,diagnostic_contract,profile)
                    self.record(dict(kind='representative_diagnostic_applied',sim=self.now(),
                        pid=os.getpid(),revision=representative_diagnostic,contract=diagnostic_contract,
                        performance_cohort=False,diagnostic_only=True))

                if frontier_representative:
                    install_frontier_representative(self,frontier_contract,profile)
                    self.record(dict(kind='frontier_representative_applied',sim=self.now(),
                        pid=os.getpid(),revision=frontier_representative,contract=frontier_contract))

            def destroy_node(self):
                try:
                    if frontier_representative:
                        self._finish_frontier_representative_recording()
                    if representative_diagnostic:
                        self._finish_representative_diagnostic_recording()
                    if navigation_budget:
                        self._finish_nominal_goal_budget_recording()
                    if navigation_pairs:
                        self._finish_mixed_frontier_pair_recording()
                    if navigation_intent:
                        self._shared_frontier_reservation.finish_recording()
                    if navigation_progress:
                        self._nav_progress_guard.finish_recording()
                finally:
                    returned = super().destroy_node()
                return returned
        configured = ConfiguredHeadquarters
    candidate = candidate_headquarters(configured, profile)
    if shared_navigation_map:
        class SharedNavigationHeadquarters(candidate):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                install_shared_navigation_map(self, shared_navigation_map)
                if shared_navigation_map == ACTIVE_ROUTE_VERSION:
                    from active_route_guard import install_active_route_guard
                    install_active_route_guard(self, contract['tolerance'])

            def record(self, event):
                if event['kind']=='rl_actual_nav2_goal_request':
                    event=dict(event, shared_navigation_goal_gate=goal_map_evidence(self,event))
                result=super().record(event)
                if shared_navigation_map!=IMMEDIATE_SHARED_MAP and event['kind']=='goal_terminal':
                    self._observe_shared_navigation_terminal(event)
                if shared_navigation_map==ACTIVE_ROUTE_VERSION and event['kind']=='goal_accepted':
                    self._observe_active_route_goal_accepted(event)
                return result
        candidate = SharedNavigationHeadquarters
    frozen.GZHeadquarters = candidate
    try:
        return consumer_controller_bootstrap.main()
    finally:
        frozen.GZHeadquarters = original


if __name__ == '__main__':
    main()
