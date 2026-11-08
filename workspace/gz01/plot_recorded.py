"""Render already-extracted metrics with existing host matplotlib; no new bag read."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(directory,case):
    result=json.loads((directory/'result.json').read_text())
    curve=result['coverage_curve']
    with np.load(directory/'reference-and-final.npz',allow_pickle=False) as data:
        obstacles=data['physical_obstacles']; origin=data['origin'];resolution=float(data['resolution'])
    bounds=[origin[0],origin[0]+obstacles.shape[1]*resolution,origin[1],origin[1]+obstacles.shape[0]*resolution]
    trajectory=[row for row in csv.DictReader((case/'trajectories.csv').open())
        if result['start_sim']<=float(row['sim_s'])<=result['end_sim']]
    figure,axes=plt.subplots(1,2,figsize=(12,4.7))
    axes[0].plot([r['elapsed_sim_s'] for r in curve],[100*r['coverage'] for r in curve],label='Strict correct free coverage')
    bad=[r for r in curve if not r['map_quality_valid']]
    axes[0].scatter([r['elapsed_sim_s'] for r in bad],[100*r['coverage'] for r in bad],s=12,c='red',label='Quality unassessed/warning')
    axes[0].axhline(95,color='grey',linestyle='--')
    coverage_label='Indoor ROI coverage (%)' if 'INDOOR-ROI' in result['scope'] else 'Reachable free-space coverage (%)'
    axes[0].set(xlabel='Elapsed Gazebo simulation seconds',ylabel=coverage_label,ylim=(0,101))
    axes[0].legend(fontsize=8);axes[0].grid(alpha=.3)
    axes[1].imshow(obstacles,origin='lower',extent=bounds,cmap='Greys',vmin=0,vmax=1)
    for robot in ('tb1','tb2','tb3'):
        rows=[row for row in trajectory if row['robot']==robot]
        axes[1].plot([float(r['x']) for r in rows],[float(r['y']) for r in rows],label=robot)
    axes[1].set(xlabel='World x (m)',ylabel='World y (m)',aspect='equal');axes[1].legend()
    figure.suptitle(result['scope']);figure.tight_layout()
    target=directory/'coverage-and-trajectories.png'
    if target.exists():raise FileExistsError(target)
    figure.savefig(target,dpi=160);plt.close(figure)
    print(json.dumps(dict(status='PASS',rendered=str(target),new_bag_reads=0,NN=0,Node=0,Gazebo=0)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--case',type=Path,required=True)
    args=parser.parse_args();main(args.directory,args.case)
