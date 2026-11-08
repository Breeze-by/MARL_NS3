"""Two preregistered public cases after fixed selection; no selection or learning."""
from collections import Counter
import json
import signal
import subprocess
import time
import traceback
import torch
from common import WORKSPACE, PROJECT, ROOT, dump, sha, configuration, Episode, Ledger, ActorCritic, load_checkpoint
from train import validate_checkpoint

CASES = [('branching_corridors-4202', 502), ('branching_corridors-4203', 501)]


def prefix_metrics(episode):
    backend = episode.env.backend
    accepted = Counter(e['robot'] for e in backend.event_log if e['kind'] == 'accepted')
    return dict(actual_joint=len(episode.records), sim=backend.sim, coverage=backend.coverage(),
        coverage_times=dict(backend.coverage_times), paths_m=dict(backend.paths), accepted=dict(accepted),
        all_robot_participation=all(accepted[r] >= 1 and backend.paths[r] >= 1. for r in ('tb1', 'tb2', 'tb3')),
        natural_complete=bool(episode.terminated and episode.info.get('reason') == 'natural_complete'),
        minimum_pair_m=backend.minimum_pair, safe_blocks=backend.safe_blocks,
        scope='at most40decisions, or earlier natural ending; before final stop, not a100decision result')


def run():
    started = time.monotonic()
    selected = json.loads((PROJECT/'runs/selection.json').read_text())['selected']
    checkpoint = ROOT/selected['checkpoint']
    if sha(checkpoint) != selected['checkpoint_sha256']:
        raise ValueError('Fixed selected checkpoint changed')
    if json.loads((checkpoint.parent/'process-exit.json').read_text())['exit_code'] != 0:
        raise ValueError('Formal parent native exit is not0')
    validate_checkpoint(checkpoint, json.loads((checkpoint.parent/'summary.json').read_text()))
    output = PROJECT/'evidence/public-regression-01'
    output.mkdir(exist_ok=False)
    config = configuration()
    ledger = Ledger(output/'ledger.jsonl', 'rl04_selected_public_regression')
    torch.set_num_threads(1)
    model = ActorCritic(ledger, config['hidden'])
    load_checkpoint(checkpoint, model, restore_rng=False)
    model.eval()
    initial = {k:p.detach().clone() for k,p in model.state_dict().items()}
    maps = json.loads((PROJECT/'evidence/corpus-01/maps.json').read_text())
    old = {}
    for path in (PROJECT/'evidence/development-02').glob('*/case.json'):
        case = json.loads(path.read_text())
        if (case['map'], case['seed']) in CASES:
            old[(case['map'], case['seed'])] = (case, path.parent/'summary.json')
    dump(output/'binding.json', dict(selected=selected, cases=CASES, max_joint_per_case=100,
        max_total_joint=200, wall_seconds=900, comparison_cap=40, optimizer_updates=0,
        source_commit=subprocess.check_output(['git', '-C', str(WORKSPACE), 'rev-parse', 'HEAD'], text=True).strip(),
        scope='public previousTEST nowTRAIN; not newTEST, not for reselecting or tuning'))
    results, comparisons, active, failure = [], [], None, None
    def timeout(signum, frame):
        raise TimeoutError('Registered900wall public regression cap,30reserved for finalization')
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.001, 870-(time.monotonic()-started)))
    try:
        for index, (name, seed) in enumerate(CASES):
            row = dict(next(r for r in maps if r['name'] == name), split='PUBLIC_REGRESSION')
            pose = next(p for p in row['positions'] if p['seed'] == seed)
            old_case, old_path = old[(name, seed)]
            if old_case['positions'] != pose['positions']:
                raise ValueError('OldDEV02 and new physical positions differ')
            active = Episode(row, pose, 800000+index, config, ledger, output/f'{index:02d}-{name}-{seed}', 'rl', fatal_idle=True)
            if active.observation['contract'] != config['observation_contract']:
                raise ValueError('Regression contract mismatch')
            prefix = None
            while not active.env.done:
                active.step(model, deterministic=True, bootstrap=False)
                if len(active.records) == 40 or (active.env.done and len(active.records) < 40):
                    prefix = prefix_metrics(active)
                    dump(active.output/'prefix40.json', prefix)
            closed, active = active, None
            results.append(closed.finish('rl04_public_regression_end'))
            baseline = json.loads(old_path.read_text())
            comparisons.append(dict(map=name, seed=seed, old_DEV02_summary=str(old_path.relative_to(ROOT)),
                old_DEV02_actual_joint=baseline['actual_joint'], old_DEV02_at_most40=baseline,
                selected_at_most40=prefix, selected_at_most100=results[-1],
                warning='OldDEV02 was capped40 or ended earlier; no claim about old weights at100'))
            print(json.dumps(results[-1]), flush=True)
        if ledger.counts['env_step'] > 200:
            raise ValueError('Registered public regression joint budget exceeded')
        if not all(torch.equal(initial[k],p) for k,p in model.state_dict().items()):
            raise ValueError('Public regression changed model weights')
    except BaseException as error:
        failure = dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc())
        dump(output/'first-failure.json', failure)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if active is not None:
            results.append(active.finish('rl04_public_regression_failure'))
        ledger.flush('public_regression_end', cases=len(results))
        dump(output/'summary.json', dict(status='PUBLIC REGRESSION COMPLETE' if failure is None else 'FAIL',
            cases=results, comparisons=comparisons, counts=dict(ledger.counts), wall_seconds=time.monotonic()-started,
            optimizer_updates=0, weights_unchanged=all(torch.equal(initial[k],p) for k,p in model.state_dict().items()),
            failure=failure, used_for_selection=False, newTEST_cases=0, gazebo_runs=0))


if __name__ == '__main__':
    run()
