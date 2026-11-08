"""Standalone figures from saved records only; no inference or environment access."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

PROJECT=Path(__file__).resolve().parents[2]


def save(fig,name):
    output=PROJECT/'figures';output.mkdir(exist_ok=True)
    fig.savefig(output/(name+'.png'),dpi=170,bbox_inches='tight')
    fig.savefig(output/(name+'.svg'),bbox_inches='tight')
    plt.close(fig)


def run():
    parent=PROJECT/'runs/formal-01'
    values=[json.loads(s) for s in (parent/'validation.jsonl').read_text().splitlines()]
    if len(values)!=4:raise ValueError('Four registered validations required')
    x=[r['after_joint_decisions'] for r in values]
    fig,axes=plt.subplots(1,3,figsize=(11,3.2))
    for ax,key,label in zip(axes,['natural_complete_rate','penalty_T95_mean','total_path_m'],
            ['VAL natural completion fraction','VAL mean T95 (s; nonreach=500)','VAL total path (m)']):
        ax.plot(x,[r[key] for r in values],marker='o');ax.set(xlabel='Training joint decisions',ylabel=label,xticks=x)
        ax.grid(alpha=.25)
    fig.suptitle('RL-03 fixed validation; one seed / one run, not a test result')
    save(fig,'training-fixed-validation')
    result=json.loads((PROJECT/'runs/test-01/comparison.json').read_text())
    arms=['rl','old_reference','traditional'];labels=['New RL','Old weights / new candidates','Traditional / new candidates']
    fig,axes=plt.subplots(1,3,figsize=(12,3.6));colors=['#2468a0','#e39b33','#668965']
    for ax,key,title in zip(axes,['complete','penalty_T95','total_path_m'],
            ['Natural completion fraction','Mean T95 (s; nonreach=500)','Mean total path (m)']):
        ax.bar(range(3),[result['descriptive'][a][key]['mean'] for a in arms],color=colors)
        ax.set(xticks=range(3),xticklabels=['New RL','Old ref.','Traditional'],title=title)
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('36 locked episodes: 6 new within-family maps x 2 positions x 3 arms')
    save(fig,'test-three-arm-summary')
    rows=result['cases'];keys=sorted({(r['map'],r['seed']) for r in rows})
    fig,ax=plt.subplots(figsize=(12,4))
    for arm,label,color in zip(arms,labels,colors):
        values=[next(r['metrics']['penalty_T95'] for r in rows if (r['map'],r['seed'])==key and r['arm']==arm) for key in keys]
        ax.plot(range(12),values,'o-',label=label,color=color,alpha=.85)
    ax.set(xticks=range(12),xticklabels=[f'{name.rsplit("-",1)[-1]}/{seed}' for name,seed in keys],
        ylabel='T95 (sim s; nonreach=500)',xlabel='Paired map seed / physical-position seed',
        title='All paired outcomes; penalty values are not actual completion times')
    ax.legend(fontsize=8);ax.grid(alpha=.2);save(fig,'test-paired-times')


if __name__=='__main__':run()
