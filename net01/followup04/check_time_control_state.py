"""Direct checks of the actual pure coordination state; no ROS/model imports."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from time_control_state import TimeControlState,QUANTUM_NS,TOKEN_WALL_PERIOD_NS


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    checks={}
    def eligible(s):return s.next_wall_ns or 0
    def can(s):return s.can_step(eligible(s))
    def finish(s,before,iteration=0):
        s.begin_step(eligible(s));s.complete_step(dict(before_ns=before,after_ns=before+QUANTUM_NS,
            before_iterations=iteration,after_iterations=iteration+10,completed_steps=10))
    s=TimeControlState();assert not can(s);s.native('ready',0)
    finish(s,5_000_000);finish(s,15_000_000,10)
    assert not can(s) and s.bootstrap_tokens==2
    checks['preanchor_at_most_two_physical_quanta']=True
    s.set_anchor(10_000_000);s.clock(20_000_000)
    assert not can(s);s.native('step',10_000_000);assert can(s)
    finish(s,25_000_000,20);assert s.physical_ns==35_000_000 and not can(s)
    checks['nonterminal_clock_phase_and_actual20ms_lead_bound']=True
    s.native('step',20_000_000);assert can(s) and s.clock_ns==20_000_000
    s.clock(30_000_000);assert can(s)
    checks['true_ACK_has_hub_actual_clock_provenance_despite_independent_BE_missing_sample']=True
    s.begin_step(eligible(s))
    try:s.begin_step(eligible(s))
    except RuntimeError:pass
    else:raise AssertionError('overlapping physical token permitted')
    s.hold();assert not can(s)
    s.complete_step(dict(before_ns=35_000_000,after_ns=45_000_000,
        before_iterations=30,after_iterations=40,completed_steps=10))
    assert s.mode=='HOLD' and not can(s)
    checks['HOLD_preempts_new_tokens_allows_only_original_inflight_completion']=True
    assert s.run();assert s.stop_observe(True) and s.mode=='STOP_COUPLED'
    assert not can(s)  # No native credit; normal stop cannot run freely.
    checks['normal_stop_observe_preserves_actual_native_credit']=True
    s.fail('actual_transport_failure');assert not s.run() and not s.stop_observe(False)
    assert s.stop_observe(True) and s.mode=='FAULT_STOP_OBSERVE' and can(s)
    finish(s,45_000_000,40);assert s.native_ns==20_000_000
    checks['failed_stop_requires_authority_exit_and_never_fakes_native_ACK']=True
    s.hold(expected_shutdown=True);s.hold();assert s.expected_shutdown and not can(s) and not s.run() and not s.stop_observe(True)
    s.native('closed',s.native_ns);assert s.failure=='actual_transport_failure'
    checks['expected_shutdown_does_not_resume_or_overwrite_firstfault']=True
    bad=TimeControlState();bad.native('ready',0);bad.begin_step(eligible(bad))
    bad.complete_step(dict(before_ns=0,after_ns=9_000_000,
        before_iterations=0,after_iterations=9,completed_steps=9))
    assert bad.failure=='post_physics_token_mismatch' and not can(bad) and not bad.stop_observe(True)
    checks['incomplete_actual_physics_is_not_ACKed_as_a_full_token']=True
    paced=TimeControlState();paced.native('ready',0);paced.run()
    paced.begin_step(100);paced.complete_step(dict(before_ns=0,after_ns=QUANTUM_NS,before_iterations=0,after_iterations=10,completed_steps=10))
    prior_deadline=paced.next_wall_ns;assert paced.run() and paced.next_wall_ns==prior_deadline
    assert not paced.can_step(100+TOKEN_WALL_PERIOD_NS-1) and paced.can_step(100+TOKEN_WALL_PERIOD_NS)
    paced.set_anchor(5_000_000);paced.clock(10_000_000)
    paced.hold();assert paced.run() and paced.next_wall_ns is None
    assert paced.native_ns==0 and paced.anchor==5_000_000
    checks['fixed20ms_wall_pacing_and_permission_restart_never_reanchors_native']=True
    result=dict(scope='Pure actual coordinator-state methods; 0ROS/GZ/native/Goal/NN',status='PASS',checks=checks)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
