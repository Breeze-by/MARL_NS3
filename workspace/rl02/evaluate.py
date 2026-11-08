"""Locked 36-episode TEST, only after both formal runs and VAL selection end."""
import argparse
import json
from pathlib import Path
import time
import traceback
import torch
from maps import HERE, ROOT, PROJECT, dump, sha
from diagnose import verify_lock, append
from execution import Episode
from train import validate_checkpoint
from multi_robot_exploration.rl_ledger import Ledger
from multi_robot_exploration.ppo import ActorCritic, load_checkpoint


def evaluate(output):
    verify_lock(HERE/'FOLLOWUP_LOCK.json')
    ready = json.loads((PROJECT/'runs/P4_READY.json').read_text())
    for path, expected in ready['code_sha256'].items():
        if sha(ROOT/path) != expected:
            raise ValueError('Reviewed TEST source changed: '+path)
    selected_path = PROJECT/'runs/selection.json'
    if ready['selection_sha256'] != sha(selected_path) or not ready['authorized_followup_evaluation']:
        raise ValueError('TEST selection is not independently bound')
    selection = json.loads(selected_path.read_text())['selected']
    checkpoint = ROOT/selection['checkpoint']
    if sha(checkpoint) != selection['checkpoint_sha256']:
        raise ValueError('Selected TEST checkpoint changed')
    for number in (1, 2):
        native = json.loads((ROOT/f'rl-02/runs/formal-{number:02d}/process-exit.json').read_text())
        run_result = json.loads((ROOT/f'rl-02/runs/formal-{number:02d}/summary.json').read_text())
        if native['exit_code'] != 0 and run_result['status'] != 'RESOURCE TRUNCATED':
            raise ValueError('A registered formal process failed outside the declared resource limit')
    if (ROOT/'rl-02/runs/FORMAL_FATAL.json').exists():
        raise RuntimeError('Formal stage fatal cannot be hidden by TEST')
    parent = json.loads((checkpoint.parent/'summary.json').read_text())
    if json.loads((checkpoint.parent/'process-exit.json').read_text())['exit_code'] != 0:
        raise ValueError('Selected checkpoint parent did not exit normally')
    validate_checkpoint(checkpoint, parent)
    config = json.loads((HERE/'config.json').read_text())
    lock = json.loads((HERE/'P1_LOCK.json').read_text())
    maps = [m for m in json.loads((ROOT/lock['maps_manifest']).read_text()) if m['split'] == 'TEST']
    if len(maps) != 6 or sum(len(m['positions']) for m in maps) != 18:
        raise ValueError('Locked TEST corpus differs from pre-registration')
    output.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(output/'ledger.jsonl', 'locked_test')
    torch.set_num_threads(config['torch_threads'])
    model = ActorCritic(ledger, config['hidden'])
    load_checkpoint(checkpoint, model, restore_rng=False)
    before = {k: v.detach().clone() for k, v in model.state_dict().items()}
    results, active = [], None
    start = time.monotonic()
    dump(output/'binding.json', dict(selected_checkpoint=selection, selection_sha256=sha(selected_path),
        ready_sha256=sha(PROJECT/'runs/P4_READY.json'), evaluation_code_sha256=sha(__file__),
        max_test_episodes=36, max_joint_per_episode=100, config=config))
    try:
        pair_index = 0
        for row in maps:
            for pose in row['positions']:
                # Same cases and actual positions for both policies. Alternate
                # order by pair, without looking at outcomes.
                kinds = ('rl', 'traditional') if pair_index % 2 == 0 else ('traditional', 'rl')
                for kind_index, kind in enumerate(kinds):
                    case = output/f'{pair_index:02d}-{row["name"]}-{pose["seed"]}-{kind}'
                    active = Episode(row, pose, 2000000+2*pair_index+kind_index, config, ledger, case, kind)
                    while not active.env.done:
                        active.step(model, deterministic=True, bootstrap=False)
                    closed, active = active, None
                    result = closed.finish('test_episode_end')
                    result['pair_index'] = pair_index
                    append(output/'episodes.jsonl', result)
                    results.append(result)
                    print(json.dumps(dict(pair=pair_index, map=row['name'], seed=pose['seed'],
                        policy=kind, coverage=result['coverage'], reason=result['end_reason'])), flush=True)
                pair_index += 1
        if len(results) != 36 or not all(torch.equal(before[k], p) for k, p in model.state_dict().items()):
            raise RuntimeError('Incomplete TEST budget or changed checkpoint weights')
    except BaseException as failure:
        dump(output/'first-failure.json', dict(type=type(failure).__name__, message=str(failure),
            traceback=traceback.format_exc(), finished_episodes=len(results)))
        raise
    finally:
        if active is not None:
            active.finish('test_failure')
        ledger.flush('locked_test_end', finished_episodes=len(results))
    dump(output/'summary.json', dict(status='LOCKED TEST EXECUTION COMPLETE', episodes=len(results),
        counts=dict(ledger.counts), optimizer_step=0, model_weights_unchanged=True,
        wall_seconds=time.monotonic()-start, selected_checkpoint_sha256=sha(checkpoint),
        formally_frozen=False, gazebo_verified=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    evaluate(parser.parse_args().output.resolve())
