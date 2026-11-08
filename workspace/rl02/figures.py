"""Report plots from complete recorded runs; never calls a policy/environment."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from maps import PROJECT, ROOT, dump


def json_lines(path):
    return [json.loads(s) for s in path.read_text().splitlines()]


def training(output):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    for column, number in enumerate((1, 2)):
        root = PROJECT/f'runs/formal-{number:02d}'
        rows = json_lines(root/'episodes.jsonl')
        x = np.cumsum([r['actual_joint'] for r in rows])
        for reason, marker, color in [('natural_complete', 'o', 'tab:green'),
                                      ('stalled_wait', 'v', 'tab:red'),
                                      ('decision_budget', 's', 'tab:purple'),
                                      ('formal_global_budget_partial_tail', 'X', 'tab:orange')]:
            selected = [i for i, r in enumerate(rows) if r['end_reason'] == reason]
            if selected:
                axes[0, column].scatter(x[selected], [rows[i]['coverage'] for i in selected],
                                       s=12 if marker != 'X' else 55, marker=marker, color=color, label=reason)
        axes[0, column].axhline(.95, ls='--', lw=.8, color='black')
        axes[0, column].set(xlabel='Cumulative formal joint steps', ylabel='Final episode coverage',
            ylim=(0, 1.02), xlim=(0, 4096), title=f'Run {number}: all episodes, including failures/tail')
        axes[0, column].legend(fontsize=7, loc='lower right')
        blocks = json_lines(root/'rollouts.jsonl')
        for head, color in enumerate(('tab:blue', 'tab:orange', 'tab:green')):
            axes[1, column].plot([r['after_joint_decisions'] for r in blocks],
                [r['per_head_actor_weight_change'][head] for r in blocks], marker='.', color=color,
                label=f'tb{head+1} actor weight delta')
        axes[1, column].set(xlabel='Formal joint steps', ylabel='Per-rollout weight change norm', xlim=(0, 4096))
        axes[1, column].legend(fontsize=8)
    fig.suptitle('RL02 recorded training: mixed TRAIN tasks; not a generalization result')
    fig.savefig(output/'training.png', dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout='constrained')
    for number, label in ((1, 'Weights-only warm start'), (2, 'Independent initialization')):
        root = PROJECT/f'runs/formal-{number:02d}'
        rows = json_lines(root/'validation.jsonl')
        for ax, metric, title in zip(axes, ('natural_complete_rate', 'mean_coverage', 'penalty_T95_mean'),
            ('VAL completion, 3 cases', 'VAL final coverage', 'VAL labeled penalty T95, sim s')):
            ax.plot([r['after_joint_decisions'] for r in rows], [r[metric] for r in rows], marker='o', label=label)
            ax.set(title=title, xlabel='Formal joint steps')
    axes[0].set_ylim(0, 1.02)
    axes[1].set_ylim(0, 1.02)
    axes[0].legend(fontsize=7)
    fig.suptitle('Fixed VAL monitoring only; 500 sim s is imputed for nonreach, not actual T95')
    fig.savefig(output/'validation.png', dpi=150)
    plt.close(fig)


def test(output):
    data = json.loads((PROJECT/'runs/test-01/comparison.json').read_text())
    rows = data['pairs']
    names = sorted({r['map'] for r in rows})
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    for kind, color, offset in (('rl', 'tab:blue', -.025), ('traditional', 'tab:orange', .025)):
        for index, row in enumerate(rows):
            x = names.index(row['map'])+[-.15, 0, .15][(row['seed']-301)]+offset
            policy = row['policies'][kind]
            axes[0].scatter(x, policy['coverage'], c=color, s=28,
                label=kind if index == 0 else None)
            reached = policy['actual_T95'] is not None
            axes[1].scatter(x, policy['penalty_T95'], c=color, marker='o' if reached else 'X', s=35)
    axes[0].axhline(.95, ls='--', lw=.8, color='black')
    axes[0].set(ylabel='Final coverage, all 18 pairs', ylim=(0, 1.02))
    axes[1].set(ylabel='T95 / labeled penalty, simulation seconds', ylim=(0, 520))
    for ax in axes:
        ax.set_xticks(range(len(names)), [n.replace('_corridors', '').replace('_chambers', '') for n in names], rotation=35, ha='right')
        ax.grid(axis='y', alpha=.2)
    axes[0].legend()
    fig.suptitle('Corrected fixed-policy TEST: 6 maps / 2 families, all 18 pairs\nX at 500 is nonreach penalty, not actual completion time')
    fig.savefig(output/'test-pairs.png', dpi=150, bbox_inches='tight')
    plt.close(fig)


def ppo_diagnostics(output):
    fig, axes = plt.subplots(3, 2, figsize=(11, 10), layout='constrained')
    results = []
    for number in (1, 2):
        root = PROJECT/f'runs/formal-{number:02d}'
        episodes = json_lines(root/'episodes.jsonl')
        updates = json_lines(root/'updates.jsonl')
        axes.flat[0].plot(np.cumsum([r['actual_joint'] for r in episodes]),
            [r['reward_total'] for r in episodes], lw=.7, label=f'Run {number}')
        axes.flat[0].set(title='Episode return, all TRAIN failures/tail included', xlabel='Formal joint steps')
        stats = {}
        for ax, key in zip(list(axes.flat)[1:], ('actor_loss', 'critic_loss', 'entropy', 'approx_kl', 'gradient_norm')):
            values = np.array([r[key] for r in updates])
            ax.plot(np.arange(len(values))+1, values, lw=.8, label=f'Run {number}')
            ax.set(title=key, xlabel='Actual Adam updates')
            stats[key] = dict(min=float(values.min()), mean=float(values.mean()), max=float(values.max()))
        clip = np.array([r['clip_fraction'] for r in updates])
        rewards = np.array([r['reward_total'] for r in episodes])
        stats['clip_fraction'] = dict(min=float(clip.min()), mean=float(clip.mean()), max=float(clip.max()))
        stats['episode_return'] = dict(min=float(rewards.min()), mean=float(rewards.mean()), median=float(np.median(rewards)), max=float(rewards.max()))
        terms = {key:sum(r['reward_terms'].get(key, 0.) for r in episodes) for key in episodes[0]['reward_terms']}
        results.append(dict(run=number, actual_Adam_updates=len(updates), diagnostics=stats,
                            summed_episode_reward_terms_including_partial_tail=terms))
    axes.flat[0].legend()
    fig.suptitle('Recorded PPO diagnostics; mixed TRAIN tasks do not show generalization')
    fig.savefig(output/'ppo-diagnostics.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    dump(PROJECT/'evidence/training-diagnostics.json', dict(runs=results, nn_forward=0,
        env_reset=0, env_step=0, optimizer_step=0, method='Read-only aggregation of saved episodes/updates; no new training.'))


def fixed_trajectory(output):
    # Chosen in source before TEST: no post-outcome selection of a favorable case.
    name, seed = 'loop_chambers-3101', 301
    lock = json.loads((PROJECT/'workspace/rl02/P1_LOCK.json').read_text())
    row = next(r for r in json.loads((ROOT/lock['maps_manifest']).read_text()) if r['name'] == name)
    projected = np.load(ROOT/lock['map_qualification']/name/'projection.npz')
    fig, axes = plt.subplots(1, 2, figsize=(11, 6), layout='constrained')
    for ax, kind in zip(axes, ('rl', 'traditional')):
        folder = next(p for p in (PROJECT/'runs/test-01').iterdir() if p.is_dir() and p.name.endswith(f'{name}-{seed}-{kind}'))
        trace = json.loads((folder/'trajectory.json').read_text())
        summary = json.loads((folder/'summary.json').read_text())
        b = row['bounds']
        ax.imshow(projected['obstacles'], origin='lower', extent=(b[0], b[2], b[1], b[3]), cmap='Greys', vmin=0, vmax=1)
        for robot, color in zip(('tb1', 'tb2', 'tb3'), ('tab:blue', 'tab:orange', 'tab:green')):
            xy = np.asarray([p['poses'][robot][:2] for p in trace])
            ax.plot(xy[:, 0], xy[:, 1], color=color, lw=1.2, label=robot)
            ax.scatter(*xy[0], c=color, marker='o', s=25)
            ax.scatter(*xy[-1], c=color, marker='^', s=35)
        ax.set(title=f'{kind}: {summary["end_reason"]}, coverage {summary["coverage"]:.3f}',
               xlabel='x (m)', ylabel='y (m)', aspect='equal')
        ax.legend(fontsize=8)
    fig.suptitle('Predeclared loop3101/start301: corrected comparison, 2D proxy, not Gazebo')
    fig.savefig(output/'fixed-test-trajectory.png', dpi=150, bbox_inches='tight')
    plt.close(fig)


def gazebo_trajectory(output):
    import csv
    from matplotlib.colors import ListedColormap
    case = PROJECT/'evidence/gazebo-rl-01'
    events = json_lines(case/'events.jsonl')
    start = next(r['sim'] for r in events if r['kind']=='smoke_initial_positions')
    end = next(r['sim'] for r in events if r['kind']=='smoke_bound')
    grid = np.load(case/'merge_map_last.npz')
    cells = grid['data'].reshape(int(grid['height']),int(grid['width']))
    ox,oy = grid['origin']; resolution=float(grid['resolution'])
    display = np.where(cells<0,0,np.where(cells==0,1,2))
    fig,axes=plt.subplots(1,2,figsize=(12,5.5),layout='constrained')
    axes[0].imshow(display,origin='lower',cmap=ListedColormap(['.7','white','black']),
        extent=(ox,ox+cells.shape[1]*resolution,oy,oy+cells.shape[0]*resolution),vmin=0,vmax=2)
    with (case/'trajectories.csv').open() as stream:
        rows=[r for r in csv.DictReader(stream) if start<=float(r['sim_s'])<=end]
    for robot,color in zip(('tb1','tb2','tb3'),('tab:blue','tab:orange','tab:green')):
        data=[r for r in rows if r['robot']==robot]
        xy=np.array([[float(r['x']),float(r['y'])] for r in data])
        axes[0].plot(xy[:,0],xy[:,1],color=color,label=robot)
        axes[0].scatter(*xy[0],color=color,marker='o',s=25)
        axes[0].scatter(*xy[-1],color=color,marker='^',s=35)
        axes[1].plot([float(r['sim_s'])-start for r in data],
            [float(r['speed_xy']) for r in data],color=color,lw=.8,label=robot)
    axes[0].set(title='Actual SLAM merge and Gazebo body paths',xlabel='x (m)',ylabel='y (m)',aspect='equal')
    axes[0].legend()
    axes[1].axhline(.26,color='black',ls='--',lw=.8,label='Nominal/proxy 0.26 m/s')
    axes[1].set(title='Actual body speed, not commanded speed',xlabel='Autonomous simulation seconds',ylabel='m/s')
    axes[1].legend(fontsize=8)
    fig.suptitle('180 sim s fixed-RL engineering smoke; not full-task or hardware certification')
    fig.savefig(output/'gazebo-actual-map-motion.png',dpi=150,bbox_inches='tight')
    plt.close(fig)


def main():
    output = PROJECT/'figures'
    output.mkdir(exist_ok=False)
    training(output)
    ppo_diagnostics(output)
    if (PROJECT/'runs/test-01/comparison.json').exists():
        test(output)
        fixed_trajectory(output)
    print(str(output))


if __name__ == '__main__':
    main()
