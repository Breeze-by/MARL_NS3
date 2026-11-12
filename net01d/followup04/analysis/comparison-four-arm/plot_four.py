"""Four saved canonical curves/GT traces only; no runtime or metric recomputation."""
import json
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(REPO/'net01d/followup02/analysis'))
from plot_case_evidence import read_csv
import matplotlib.pyplot as plt
import numpy as np


def main():
    base=REPO/'net01d/followup04';out=Path(__file__).resolve().parent
    specs=[('A0','gz-simhealth-a0-01','#b33c35','-.','valid task metrics; controller1 FAIL'),
        ('A1','gz-simhealth-a1-03','#1767a6','-','limited original engineering scope'),
        ('B02','gz-simhealth-b1-02','#cd741b','--','real Wi-Fi, actual recorded exits0'),
        ('C','gz-simhealth-c1-01','#3b8461',':','fixed constrained Wi-Fi; controller0')]
    arms=[];inputs=[]
    for label,case,color,style,note in specs:
        analysis=base/'analysis'/case
        paths=[analysis/'metrics/result.json',analysis/'metrics/coverage.csv',base/'runs'/case/'trajectories.csv']
        metric=json.loads(paths[0].read_text());curve=read_csv(paths[1])
        trajectory=[r for r in read_csv(paths[2]) if metric['start_sim']<=float(r['sim_s'])<=metric['end_sim']]
        arms.append(dict(label=label,case=case,color=color,style=style,note=note,metric=metric,curve=curve,trajectory=trajectory))
        inputs.extend(str(p) for p in paths)
    reference=base/'analysis/gz-simhealth-a1-03/metrics/reference-and-final.npz'
    with np.load(reference,allow_pickle=False) as ref:
        obstacles=ref['physical_obstacles'];origin=ref['origin'];resolution=ref['resolution']
    extent=[origin[0],origin[0]+obstacles.shape[1]*resolution,origin[1],origin[1]+obstacles.shape[0]*resolution]
    xs=[float(r['x']) for a in arms for r in a['trajectory']];ys=[float(r['y']) for a in arms for r in a['trajectory']]
    limits=[min(xs)-.8,max(xs)+.8,min(ys)-.8,max(ys)+.8]
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
    fig=plt.figure(figsize=(16,14));grid=fig.add_gridspec(3,2,height_ratios=[.95,1.15,1.15],hspace=.34,wspace=.16)
    ax=fig.add_subplot(grid[0,:])
    for a in arms:
        m=a['metric'];rows=a['curve'];x=[float(r['elapsed_sim_s']) for r in rows];y=[100*float(r['coverage']) for r in rows]
        t=m['quality_valid_thresholds']['0.95']['elapsed_sim_s']
        ax.step(x,y,where='post',color=a['color'],linestyle=a['style'],lw=1.6,
            label=f"{a['label']}: T95 {t:.2f} sim s"+(' | controller1 FAIL' if a['label']=='A0' else ''))
        bad=[r for r in rows if r['map_quality_valid']!='True']
        ax.scatter([float(r['elapsed_sim_s']) for r in bad],[100*float(r['coverage']) for r in bad],marker='x',s=18,color=a['color'],lw=.8)
        ax.scatter([t],[95],marker='*',s=100,color=a['color'],edgecolors='white',lw=.5,zorder=5)
    for threshold in [90,95]:ax.axhline(threshold,color='#888888',ls=':',lw=.7)
    ax.set(title='Original R primary coverage | fixed ROI: 15,558 cells | x = quality-invalid sample',
        xlabel='Simulation seconds since each original autonomous phase start',ylabel='Correct free-space coverage (%)',xlim=[0,180],ylim=[0,102])
    ax.grid(alpha=.18);ax.legend(loc='lower right',fontsize=10)
    counts={}
    for index,a in enumerate(arms):
        ax=fig.add_subplot(grid[1+index//2,index%2]);ax.imshow(obstacles,origin='lower',extent=extent,cmap='Greys',vmin=0,vmax=1,alpha=.5)
        counts[a['case']]={}
        for robot,color in [('tb1','#1767a6'),('tb2','#d97706'),('tb3','#38865b')]:
            rows=[r for r in a['trajectory'] if r['robot']==robot];counts[a['case']][robot]=len(rows)
            x=[float(r['x']) for r in rows];y=[float(r['y']) for r in rows]
            ax.plot(x,y,color=color,lw=1.25,label=f"{robot}: {a['metric']['robot_metrics'][robot]['path_m']:.2f} m")
            ax.scatter(x[0],y[0],s=24,facecolors='white',edgecolors=color,zorder=4);ax.scatter(x[-1],y[-1],s=22,marker='s',color=color,zorder=4)
        ax.set(title=a['label']+' | '+a['note'],xlabel='World x (m)',ylabel='World y (m)',aspect='equal',xlim=limits[:2],ylim=limits[2:])
        ax.grid(alpha=.14);ax.legend(loc='lower left',fontsize=9)
    fig.suptitle('Four single episodes under the new simhealth contract',fontsize=17,y=.982)
    fig.text(.065,.952,'A0 task-window metrics are valid; its controller exited1. No whole-project GO or RF/algorithm superiority claim.',fontsize=11,color='#9b2c2c')
    fig.text(.065,.045,'GT is offline diagnostic only, never Policy input. Open circles=start; squares=last in-phase sample. No padded curve/trajectory endpoints.',fontsize=10)
    fig.text(.065,.025,'A0/B02: aae; A1-03: 2be; C: bd663. Poststop/report/observation deltas disclosed. Different paths and input availability; one episode per arm.',fontsize=10)
    fig.subplots_adjust(left=.065,right=.98,bottom=.08,top=.92)
    files=[]
    for suffix in ['png','svg']:
        target=out/('coverage-and-gt-four-arm.'+suffix);fig.savefig(target,dpi=170,facecolor='white');files.append(str(target))
    plt.close(fig)
    manifest=dict(status='PLOT_ONLY_NO_METRIC_CHANGE',inputs=inputs,reference=str(reference),files=files,
        data_scope='Existing canonical result/CSV and original in-phase GTCSV only; original mapquality/ROI15558/phase unchanged',
        sources=dict(A0='aae271f',A1='2be7e229',B02='aae271f',C='bd663824'),
        A0='PROCESS_INTEGRITY_FAIL_controller1; valid task metrics do not override failure',
        limitations='Singleepisode/differentpaths/inputavailability; not pureRF/CPU causality or superiority; no physical/metric rule change',
        trajectory_counts=counts,bag_reads=0,Gateway_reads=0,native_reads=0,PCAP_reads=0,Torch_imports=0,new_models=0)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(dict(files=files,status=manifest['status'])))


if __name__=='__main__':main()
