"""Predeclared VAL-only selection after both registered native processes end."""
import json
from pathlib import Path
import sys
from maps import HERE, PROJECT, dump, sha
from train import validate_checkpoint


def select():
    root = PROJECT/'runs'
    target = root/'selection.json'
    if target.exists():
        raise FileExistsError('Selection is already sealed')
    if (root/'FORMAL_FATAL.json').exists():
        raise RuntimeError('Shared formal stage failed; no automatic TEST selection')
    eligible, excluded = [], []
    for number in (1, 2):
        case = root/f'formal-{number:02d}'
        summary = json.loads((case/'summary.json').read_text())
        native = json.loads((case/'process-exit.json').read_text())
        if native['exit_code'] != 0 or summary['status'] != 'BOUNDED TRAINING PASS':
            excluded.append(dict(run=number, reason=summary['status'], native_exit=native['exit_code']))
            continue
        for steps in (1024, 2048, 3072, 4096):
            path = case/f'checkpoint-{steps:05d}.pt'
            validate_checkpoint(path, summary)
            val = json.loads((case/'validation'/f'{steps:05d}'/'summary.json').read_text())
            if len(val['cases']) != 3 or val['optimizer_steps'] != 0 or not val['model_weights_unchanged']:
                raise ValueError('Incomplete or changed-parameter validation')
            eligible.append(dict(run=number, joint=steps, checkpoint=str(path.relative_to(PROJECT.parent)),
                checkpoint_sha256=sha(path), natural_complete_rate=val['natural_complete_rate'],
                mean_coverage=val['mean_coverage'], penalty_T95_mean=val['penalty_T95_mean'],
                total_path_m=val['total_path_m']))
    if not eligible:
        raise RuntimeError('No successful-parent registered checkpoint')
    ordered = sorted(eligible, key=lambda v: (-v['natural_complete_rate'], -v['mean_coverage'],
        v['penalty_T95_mean'], v['total_path_m'], v['joint'], v['run']))
    dump(target, dict(status='VAL-SELECTED PENDING TEST AND EXECUTION REVIEW', selected=ordered[0],
        all_candidates=ordered, excluded_runs=excluded, source='predeclared VAL lexicographic rule; no TEST',
        formally_frozen=False, test_rollouts_before_selection=0, selection_code_sha256=sha(__file__)))
    print(json.dumps(ordered[0], indent=2))


if __name__ == '__main__':
    select()
