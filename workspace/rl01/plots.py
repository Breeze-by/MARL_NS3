"""Standalone figures from saved data only; no environment or model execution."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main(training, evaluation, output):
    output.mkdir(parents=True, exist_ok=False)
    train = json.loads(training.read_text())
    result = json.loads(evaluation.read_text())
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.4), constrained_layout=True)
    episodes = train['episodes']
    full = [r for r in episodes if r['complete_record']]
    partial = [r for r in episodes if not r['complete_record']]
    axes[0].plot([r['episode'] for r in full], [r['reward'] for r in full], '.', ms=3, label='Completed episode')
    axes[0].plot([r['episode'] for r in partial], [r['reward'] for r in partial], 'x', color='tab:orange', label='Global budget tail')
    axes[0].set(xlabel='Episode', ylabel='Return', title='One bounded training run')
    axes[1].plot([r['episode'] for r in full], [r['coverage'] for r in full], '.', ms=3)
    axes[1].plot([r['episode'] for r in partial], [r['coverage'] for r in partial], 'x', color='tab:orange')
    axes[0].legend(fontsize=7)
    axes[1].axhline(.95, color='black', lw=.7, ls='--')
    axes[1].set(xlabel='Episode', ylabel='Observed reference fraction', ylim=(0, 1), title='Fixed 2D task only')
    names = list(train['actor_head_weight_changes'])
    axes[2].bar(names, list(train['actor_head_weight_changes'].values()))
    axes[2].set(ylabel='Initial-to-final L2 change', title='Actor output weights')
    fig.savefig(output/'training.png', dpi=180)
    fig.savefig(output/'training.pdf')
    plt.close(fig)
    labels = [(m, s) for m in ('A', 'B') for s in (11, 29)]
    policies = ('trained', 'traditional', 'initial')
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.7), constrained_layout=True)
    for j, policy in enumerate(policies):
        selected = [next(r for r in result['table'] if (r['map'], r['seed'], r['policy']) == (m, s, policy)) for m, s in labels]
        x = np.arange(4)+(j-1)*.25
        axes[0].bar(x, [r['coverage'] for r in selected], .24, label=policy)
        axes[1].bar(x, [r['time_95'] if r['time_95'] is not None else np.nan for r in selected], .24, label=policy)
        axes[2].bar(x, [r['total_path_m'] for r in selected], .24, label=policy)
    for ax in axes:
        ax.set_xticks(range(4), [f'{m}/{s}' for m, s in labels])
        ax.set_xlabel('Map / fixed seed')
    axes[0].set(ylabel='Observed reference fraction', ylim=(0, 1), title='Final coverage')
    axes[1].set(ylabel='Simulation seconds', title='Time to 95% (missing = unfinished)')
    axes[2].set(ylabel='Metres', title='Total actual proxy path')
    axes[0].legend(fontsize=8)
    fig.suptitle('Twelve development episodes; no statistical significance claim', fontsize=10)
    fig.savefig(output/'development-evaluation.png', dpi=180)
    fig.savefig(output/'development-evaluation.pdf')
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--training', type=Path, required=True)
    parser.add_argument('--evaluation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    main(args.training, args.evaluation, args.output)
