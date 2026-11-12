"""Plot sealed canonical CSVs and the one-pass event cache; no ROS/model calls."""
from pathlib import Path
import csv
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parent
summary = json.loads((ROOT / 'SUMMARY.json').read_text())
output = ROOT / 'figures'
output.mkdir(exist_ok=False)
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
colors = {1: '#2166ac', 2: '#d36d1f', 3: '#24916d'}
fig, axes = plt.subplots(1, 2, figsize=(13.6, 5.6), sharex=True)
for row in summary['rows']:
    path = ROOT / 'gz-analysis' / row['case'] / 'metrics/coverage.csv'
    with path.open() as stream:
        curve = list(csv.DictReader(stream))
    valid = [v for v in curve if v['map_quality_valid'] == 'True']
    invalid = [v for v in curve if v['map_quality_valid'] != 'True']
    style = '--' if row['arm'] == 'A1' else '-'
    label = f"Pair {row['pair']} {row['arm']}"
    for ax in axes:
        ax.step([float(v['elapsed_sim_s']) for v in valid],
                [100 * float(v['coverage']) for v in valid], where='post',
                color=colors[row['pair']], linestyle=style, linewidth=1.8, label=label)
        ax.scatter([float(v['elapsed_sim_s']) for v in invalid],
                   [100 * float(v['coverage']) for v in invalid],
                   marker='x', s=13, color=colors[row['pair']], alpha=.35)
        for key, level, marker in [('T95_sim_s', 95, 'o'), ('T98_sim_s', 98, 's')]:
            ax.scatter(row[key], level, marker=marker, s=30,
                       facecolors='white', edgecolors=colors[row['pair']], zorder=6)
for ax in axes:
    ax.set_xlim(0, 180)
    ax.set_xlabel('Elapsed simulation time since autonomous T0 (s)')
    ax.grid(alpha=.2)
    for level in (95, 98):
        ax.axhline(level, color='#777777', linewidth=.7, alpha=.5)
axes[0].set_ylim(0, 101)
axes[0].set_ylabel('Correct free-space coverage (%)')
axes[0].set_title('Complete received-map record')
axes[0].legend(loc='lower right', ncol=2, fontsize=9)
axes[1].set_ylim(90, 100.15)
axes[1].set_title('90-100% detail: T95 and T98 can order differently')
fig.suptitle('Fixed-policy exploration: three A1 / Wi-Fi B pairs', fontsize=15, y=.98)
fig.subplots_adjust(left=.065, right=.985, bottom=.20, top=.85, wspace=.18)
fig.text(.065, .07, 'Step-held quality-valid samples; x = invalid sample; circle/square = original quality-valid T95/T98.\nOne scene and fixed seeds; descriptive repeats, not pure-RF causal evidence. No extrapolation beyond last map sample.', fontsize=9)
for extension in ('png', 'svg'):
    fig.savefig(output / ('coverage-six.' + extension), dpi=170)
plt.close(fig)

cache = {r['case']: json.loads((ROOT / 'event-cache' / (r['case'] + '.json')).read_text()) for r in summary['rows']}
reference = np.load(ROOT / 'gz-analysis' / summary['rows'][0]['case'] / 'metrics/reference-and-final.npz')
obstacles, origin, resolution = reference['physical_obstacles'], reference['origin'], float(reference['resolution'])
extent = [float(origin[0]), float(origin[0]) + obstacles.shape[1] * resolution,
          float(origin[1]), float(origin[1]) + obstacles.shape[0] * resolution]
fig, axes = plt.subplots(1, 3, figsize=(14.8, 5.8), sharex=True, sharey=True)
robot_colors = {'tb1': '#2166ac', 'tb2': '#d36d1f', 'tb3': '#24916d'}
for pair, ax in enumerate(axes, 1):
    ax.imshow(np.ma.masked_where(~obstacles, obstacles), extent=extent, origin='lower',
              cmap='Greys', vmin=0, vmax=1, alpha=.25, interpolation='nearest')
    for row in [r for r in summary['rows'] if r['pair'] == pair]:
        data = cache[row['case']]
        style, marker = ('--', 'o') if row['arm'] == 'A1' else ('-', 's')
        for robot, points in data['trajectories_by_robot'].items():
            task = [v for v in points if row['T0_G'] <= v['sim_s'] <= row['T0_G'] + 180]
            tail = [v for v in points if data['T95_receipt_G'] <= v['sim_s'] <= data['T98_receipt_G']]
            ax.plot([v['x'] for v in task], [v['y'] for v in task], color=robot_colors[robot],
                    linestyle=style, linewidth=.8, alpha=.5)
            ax.plot([v['x'] for v in tail], [v['y'] for v in tail], color=robot_colors[robot],
                    linestyle=style, linewidth=2.5)
        for goal in data['goals']:
            target = goal['request']['event']['merge_map_target']
            raw = None if goal['result'] is None else goal['result']['event']['raw_status']
            ax.scatter(*target, marker='x' if raw == 6 else marker, s=22 if raw == 6 else 12,
                       color='#b2182b' if raw == 6 else robot_colors[goal['robot']], alpha=.8)
    ax.set_title(f"Pair {pair}: " + ('B then A1' if pair == 2 else 'A1 then B'))
    ax.set_aspect('equal')
    ax.set_xlabel('Common / world x (m)')
    ax.grid(alpha=.12)
axes[0].set_ylabel('Common / world y (m)')
handles = [Line2D([0], [0], color=color, linestyle=style, label=f'{robot} {arm}')
           for robot, color in robot_colors.items() for arm, style in [('A1', '--'), ('B', '-')]]
handles.append(Line2D([0], [0], color='#b2182b', marker='x', linestyle='', label='Raw Nav2 ABORTED goal'))
fig.legend(handles=handles, loc='lower center', ncol=7, fontsize=9, bbox_to_anchor=(.5, .10))
fig.suptitle('Recorded Gazebo motion and actual dispatched goals', fontsize=15, y=.98)
fig.subplots_adjust(left=.055, right=.985, bottom=.25, top=.87, wspace=.10)
fig.text(.055, .04, 'Thin = complete task motion; thick = motion between that case T95 and T98; markers = dispatched goals.\nGray geometry is evaluation-only truth. Region traversal is context, not exclusive sensor-credit or RF attribution.', fontsize=9)
for extension in ('png', 'svg'):
    fig.savefig(output / ('routes-three-pairs.' + extension), dpi=170)
plt.close(fig)
print('Created coverage-six and routes-three-pairs PNG/SVG from sealed caches only')
