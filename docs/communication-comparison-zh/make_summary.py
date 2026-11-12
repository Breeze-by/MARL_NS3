"""Re-label existing sealed results in Chinese. No runtime/metric re-analysis."""
from pathlib import Path
import csv
import json
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT/'net01d/followup04'
NEW = ROOT/'net01e/followup04'
FIG = HERE/'figures'
DATA = HERE/'data'
FONT = font_manager.FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams.update({'font.family': FONT.get_name(), 'font.size': 11,
                     'svg.fonttype': 'none', 'axes.unicode_minus': False,
                     'axes.spines.top': False, 'axes.spines.right': False})
MODE = {'A0':'ROS直接通信', 'A1':'本地网关', 'B':'高质量Wi-Fi', 'C':'受限Wi-Fi'}
COLORS = {'A0':'#2166AC', 'A1':'#238568', 'B':'#D27A29', 'C':'#8860A0'}
ROBOTS = {'tb1':('#2166AC','机器人1'), 'tb2':('#D27A29','机器人2'), 'tb3':('#238568','机器人3')}
SPECS = [('A0','gz-simhealth-a0-01'), ('A1','gz-simhealth-a1-03'),
         ('B','gz-simhealth-b1-02'), ('C','gz-simhealth-c1-01')]


def read_csv(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def save(fig, stem):
    for suffix in ('png','svg'):
        fig.savefig(FIG/f'{stem}.{suffix}', dpi=240, facecolor='white')
    plt.close(fig)


def load_old(mode, case):
    directory=OLD/'analysis'/case/'metrics'
    m=json.loads((directory/'result.json').read_text())
    points=read_csv(OLD/'runs'/case/'trajectories.csv')
    return dict(mode=mode, case=case, metric=m, curve=read_csv(directory/'coverage.csv'),
                trajectory=[p for p in points if m['start_sim']<=float(p['sim_s'])<=m['end_sim']])


def curve(ax, rows, label, color, style='-', t95=None, t98=None):
    valid=[r for r in rows if r['map_quality_valid']=='True']
    bad=[r for r in rows if r['map_quality_valid']!='True']
    ax.step([float(r['elapsed_sim_s']) for r in valid], [float(r['coverage'])*100 for r in valid],
            where='post', color=color, ls=style, lw=1.8, label=label)
    ax.scatter([float(r['elapsed_sim_s']) for r in bad], [float(r['coverage'])*100 for r in bad],
               marker='x', s=17, color=color, alpha=.45, linewidths=.8)
    for t,level,marker in [(t95,95,'o'),(t98,98,'s')]:
        if t is not None:
            ax.scatter(t,level,marker=marker,s=38,facecolors='white',edgecolors=color,zorder=5)


def coverage_axes(axes):
    for ax in axes:
        for level in (90,95,98):
            ax.axhline(level,color='#8A929A',ls=':',lw=.7,alpha=.7)
        ax.set(xlim=(0,180),xlabel='自主探索开始后的仿真时间（秒）')
        ax.grid(alpha=.16)
    axes[0].set(ylim=(0,102),ylabel='正确观测到的可达自由空间比例（%）',title='完整任务窗口')
    axes[1].set(ylim=(90,100.15),title='90%—100%局部放大')


def cover_old(arms):
    fig,axes=plt.subplots(1,2,figsize=(14,6.1))
    for arm,style in zip(arms,['-','--','-.',':']):
        mode,m=arm['mode'],arm['metric']
        note='（结束时报错）' if mode=='A0' else ''
        for ax in axes:
            curve(ax,arm['curve'],MODE[mode]+note,COLORS[mode],style,
                  threshold(m,.95),threshold(m,.98))
    coverage_axes(axes)
    axes[0].legend(loc='lower right',fontsize=10)
    fig.suptitle('早期四种通信方式：各一次真实Gazebo探索',fontsize=17,y=.98)
    fig.subplots_adjust(left=.075,right=.985,bottom=.24,top=.84,wspace=.18)
    fig.text(.075,.115,'圆点：达到95%；方点：达到98%；叉号：地图质量不合格的原始样本，不参与有效阈值判定。',fontsize=10)
    fig.text(.075,.065,'曲线只连接质量有效的接收样本，不补到180秒；四组并非完全相同源码，不能据此计算纯无线损失。',fontsize=10,color='#606E7B')
    save(fig,'01-早期四种通信方式-覆盖率')


def threshold(metric, level):
    value=metric['quality_valid_thresholds'].get(str(level))
    return None if value is None else value['elapsed_sim_s']


def map_background(ax, background):
    obstacles,extent=background
    ax.imshow(np.ma.masked_where(~obstacles,obstacles),origin='lower',extent=extent,
              cmap='Greys',vmin=0,vmax=1,alpha=.37,interpolation='nearest')
    ax.set(xlim=(-5.8,7.25),ylim=(-5.6,5.3),aspect='equal',
           xlabel='场景横向位置（米）',ylabel='场景纵向位置（米）')
    ax.grid(alpha=.12)


def motion(ax, by_robot, paths, tail=None):
    for robot,(color,label) in ROBOTS.items():
        points=by_robot[robot]
        x=[float(p['x']) for p in points];y=[float(p['y']) for p in points]
        ax.plot(x,y,color=color,lw=1.2,label=f'{label}：{paths[robot]:.2f}米',alpha=.8)
        if tail is not None:
            sub=[p for p in points if tail[0]<=float(p['sim_s'])<=tail[1]]
            ax.plot([p['x'] for p in sub],[p['y'] for p in sub],color=color,lw=2.8)
        ax.scatter(x[0],y[0],s=38,facecolors='white',edgecolors=color,zorder=5)
        ax.scatter(x[-1],y[-1],s=26,color=color,marker='s',zorder=5)
    ax.legend(loc='upper right',fontsize=9,framealpha=.9)


def paths_old(arms, background):
    fig,axes=plt.subplots(2,2,figsize=(12,11.5))
    for a,ax in zip(arms,axes.flat):
        map_background(ax,background)
        paths={r:v['path_m'] for r,v in a['metric']['robot_metrics'].items()}
        motion(ax,{r:[p for p in a['trajectory'] if p['robot']==r] for r in ROBOTS},paths)
        note='；结束时控制器报错' if a['mode']=='A0' else ''
        ax.set_title(MODE[a['mode']]+note,fontsize=12)
    fig.suptitle('早期四种通信方式：三机器人实际运动轨迹',fontsize=17,y=.985)
    fig.subplots_adjust(left=.07,right=.985,bottom=.13,top=.93,hspace=.26,wspace=.14)
    fig.text(.07,.065,'空心圆为起点，实心方块为任务窗口内最后位置；灰色为评价用障碍物参考。',fontsize=10)
    fig.text(.07,.035,'轨迹来自Gazebo记录，不是规划路径；参考真值仅用于评价，不进入策略。路程统计覆盖整个180秒窗口。',fontsize=10,color='#606E7B')
    save(fig,'02-早期四种通信方式-机器人轨迹')


def cover_new(rows):
    fig,axes=plt.subplots(1,2,figsize=(14.8,6.3))
    for row in rows:
        label=f'第{row["pair"]}轮 · {MODE[row["arm"]]}'
        samples=read_csv(NEW/'gz-analysis'/row['case']/'metrics/coverage.csv')
        for ax in axes:
            curve(ax,samples,label,COLORS[row['arm']],['-','--',':'][row['pair']-1],
                  row['T95_sim_s'],row['T98_sim_s'])
    coverage_axes(axes)
    axes[0].legend(loc='lower right',ncol=2,fontsize=9.5)
    fig.suptitle('最近共同版本：本地网关与高质量Wi-Fi各重复三次',fontsize=17,y=.98)
    fig.subplots_adjust(left=.075,right=.985,bottom=.24,top=.84,wspace=.18)
    fig.text(.075,.115,'绿色：本地网关；橙色：高质量Wi-Fi。线型区分轮次；圆点/方点分别表示达到95%/98%。',fontsize=10)
    fig.text(.075,.065,'只有一个走廊场景、固定种子；同样源码不代表每次观察、候选或路线相同。结果不表示Wi-Fi具有加速收益。',fontsize=10,color='#606E7B')
    save(fig,'03-最近六次重复-覆盖率')


def paths_new(rows,background):
    fig,axes=plt.subplots(3,2,figsize=(12.5,16.2))
    for row in rows:
        ax=axes[row['pair']-1,0 if row['arm']=='A1' else 1]
        d=json.loads((NEW/'event-cache'/f'{row["case"]}.json').read_text())
        map_background(ax,background)
        points={r:[p for p in values if row['T0_G']<=p['sim_s']<=row['T0_G']+180]
                for r,values in d['trajectories_by_robot'].items()}
        paths={r:row[f'path_{r}_m'] for r in ROBOTS}
        motion(ax,points,paths,tail=(d['T95_receipt_G'],d['T98_receipt_G']))
        for goal in d['goals']:
            target=goal['request']['event']['merge_map_target']
            failed=goal['result'] is not None and goal['result']['event']['raw_status']==6
            ax.scatter(*target,marker='x' if failed else '^',s=45 if failed else 16,
                       color='#BB263D' if failed else ROBOTS[goal['robot']][0],alpha=.85,zorder=4)
        ax.set_title(f'第{row["pair"]}轮 · {MODE[row["arm"]]}\n达到95%：{row["T95_sim_s"]:.2f}秒；达到98%：{row["T98_sim_s"]:.2f}秒',fontsize=11)
    fig.suptitle('最近三轮配对：真实轨迹、探索后段与实际目标',fontsize=17,y=.992)
    fig.subplots_adjust(left=.07,right=.985,bottom=.095,top=.94,hspace=.34,wspace=.17)
    fig.text(.07,.050,'细线：完整任务轨迹；粗线：本回合95%至98%覆盖期间轨迹；空心圆/方块：起点/最后位置。',fontsize=10)
    fig.text(.07,.028,'三角形：实际发送目标；红叉：导航失败目标。目标按共享地图坐标绘制，不作平移拟合；灰色真值仅供评价。',fontsize=10,color='#606E7B')
    save(fig,'04-最近六次重复-机器人轨迹')


def failed_history(early,background):
    local,failed=early
    fig,axes=plt.subplots(1,3,figsize=(17.5,6.6),gridspec_kw={'width_ratios':[1.25,1,1]})
    for arm,label,color in [(local,'本地网关（早期参考）',COLORS['A1']),
                             (failed,'早期Wi-Fi（退出异常）','#AE4F58')]:
        curve(axes[0],arm['curve'],label,color,t95=threshold(arm['metric'],.95),t98=threshold(arm['metric'],.98))
    axes[0].set(xlim=(0,180),ylim=(0,102),xlabel='自主探索后的仿真时间（秒）',
                ylabel='正确自由空间覆盖率（%）',title='任务期覆盖曲线')
    axes[0].grid(alpha=.15);axes[0].legend(loc='lower right',fontsize=9)
    for a,ax,label in [(local,axes[1],'本地网关参考'),(failed,axes[2],'Wi-Fi：停后退出异常')]:
        map_background(ax,background)
        motion(ax,{r:[p for p in a['trajectory'] if p['robot']==r] for r in ROBOTS},
               {r:v['path_m'] for r,v in a['metric']['robot_metrics'].items()})
        ax.set_title(label,fontsize=12)
    fig.suptitle('保留的早期失败回合：探索达到高覆盖，不等于整个运行正常完成',fontsize=17,y=.98)
    fig.subplots_adjust(left=.055,right=.985,bottom=.23,top=.85,wspace=.24)
    fig.text(.055,.105,'该Wi-Fi回合达到95%用时65.43仿真秒，但网关退出时被强制终止；不得与后续65.84秒回合混为一次。',fontsize=10,color='#A23D46')
    fig.text(.055,.055,'本图仅归档历史；其中本地网关参考与早期四组表为同一回合，不重复计入样本。',fontsize=10,color='#606E7B')
    save(fig,'05-保留的早期退出异常回合')


def number(value,digits=2):
    return '未达到' if value is None else f'{float(value):.{digits}f}'


def markdown_table(headers,rows):
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|']+
                     ['|'+'|'.join(map(str,row))+'|' for row in rows])


def write_data(filename,headers,rows):
    with (DATA/filename).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(headers);w.writerows(rows)


def make_document(old,new,failed):
    old_rows=[]
    old_paths=[]
    for a in old:
        m=a['metric'];paths=[m['robot_metrics'][r]['path_m'] for r in ROBOTS]
        succeeded=sum(v['succeeded'] for v in m['robot_metrics'].values())
        goals=sum(v['goals'] for v in m['robot_metrics'].values())
        state='180秒预算结束；控制器退出时报错' if a['mode']=='A0' else '180秒预算结束；停稳并正常收尾'
        old_rows.append([MODE[a['mode']],*[number(threshold(m,t)) for t in [.9,.95,.98]],
                         number(m['final_coverage']*100,4),f'{succeeded}/{goals}',state])
        old_paths.append([MODE[a['mode']],*[number(v) for v in paths],number(sum(paths)),number(m['autonomous_wall_s'],1)])
    new_rows=[];new_paths=[];pairs=[];stats=[]
    for r in new:
        new_rows.append([f'第{r["pair"]}轮',MODE[r['arm']],*[number(r[k]) for k in ['T90_sim_s','T95_sim_s','T98_sim_s']],
                         number(r['final_coverage_pct'],4),f'{r["raw_succeeded"]}/{r["goals"]}',r['raw_aborted']])
        new_paths.append([f'第{r["pair"]}轮',MODE[r['arm']],*[number(r[f'path_{robot}_m']) for robot in ROBOTS],
                          number(r['total_path_m']),number(r['autonomy_wall_s'],1)])
    for p in range(1,4):
        a=next(r for r in new if r['pair']==p and r['arm']=='A1');b=next(r for r in new if r['pair']==p and r['arm']=='B')
        pairs.append([f'第{p}轮','网关→Wi-Fi' if p!=2 else 'Wi-Fi→网关',
                      f'{b["T95_sim_s"]-a["T95_sim_s"]:+.2f}',f'{b["T98_sim_s"]-a["T98_sim_s"]:+.2f}'])
    for mode in ['A1','B']:
        rr=[r for r in new if r['arm']==mode]
        stats.append([MODE[mode],3,number(statistics.mean(r['T95_sim_s'] for r in rr)),
                      number(statistics.median(r['T95_sim_s'] for r in rr)),
                      f'{min(r["T95_sim_s"] for r in rr):.2f}—{max(r["T95_sim_s"] for r in rr):.2f}',
                      number(statistics.mean(r['T98_sim_s'] for r in rr)),
                      number(statistics.mean(r['total_path_m'] for r in rr))])
    h_old=['通信方式','达到90%（仿真秒）','达到95%（仿真秒）','达到98%（仿真秒）','最后有效覆盖率（%）','成功目标/已发目标','结束情况']
    h_new=['配对轮次','通信方式','达到90%（仿真秒）','达到95%（仿真秒）','达到98%（仿真秒）','最后有效覆盖率（%）','成功目标/已发目标','导航失败数']
    h_paths=['通信方式','机器人1路程（米）','机器人2路程（米）','机器人3路程（米）','合计路程（米）','任务期实际耗时（秒）']
    h_new_paths=['配对轮次',*h_paths]
    h_stats=['通信方式','回合数','达到95%均值（秒）','达到95%中位数（秒）','达到95%范围（秒）','达到98%均值（秒）','全窗平均路程（米）']
    h_pairs=['配对','实际先后顺序','Wi-Fi减网关：达到95%时间差（秒）','Wi-Fi减网关：达到98%时间差（秒）']
    for name,h,rows in [('早期四种方式.csv',h_old,old_rows),('最近六次覆盖与目标.csv',h_new,new_rows),
                         ('早期机器人路程.csv',h_paths,old_paths),('最近六次机器人路程.csv',h_new_paths,new_paths),
                         ('最近两种方式汇总.csv',h_stats,stats),('最近三次配对差值.csv',h_pairs,pairs)]:
        write_data(name,h,rows)
    mapping=markdown_table(['本文名称','旧记录代号','实际数据路径','如何理解'],[
        ['ROS直接通信','A0','机器人与中央控制器的业务通过原ROS/DDS直接交互','工程参考，不等于零延时或绝对成功'],
        ['本地网关','A1','保留业务代理、编码解码及Action管理；使用有序可靠的本地后端','包含网关成本，不经过模拟Wi-Fi'],
        ['高质量Wi-Fi','B（旧成功回合也写B02）','关键业务经过网关及真实ns-3 Wi-Fi MAC/PHY','链路条件较好，仍有队列、协议与传输成本'],
        ['受限Wi-Fi','C','同类业务路径，采用事前固定的受限无线配置','无线配置不同，不保证每次探索一定更慢']])
    sources=markdown_table(['本汇总内容','原始入口'],[
        ['早期四组图及配置差异','[原绘图索引](../../net01d/followup04/analysis/comparison-four-arm/manifest.json)'],
        *[[MODE[a['mode']],f'[原结果](../../net01d/followup04/analysis/{a["case"]}/RESULT.md) · [原指标](../../net01d/followup04/analysis/{a["case"]}/metrics/result.json)'] for a in old],
        ['最近六次共同版本结果','[原报告](../../net01e/followup04/REPORT.md) · [逐回合表](../../net01e/followup04/TRIALS.csv) · [配对表](../../net01e/followup04/PAIRS.csv)'],
        ['早期网关阶段耗时','[原耗时摘要](../../net01d/followup04/analysis/costs-four-arm-01/SUMMARY.md)'],
        ['早期ns-3模型服务耗时','[原模型耗时摘要](../../net01d/followup04/analysis/native-costs-01/SUMMARY.md)'],
        ['保留的早期Wi-Fi退出异常回合','[原结果](../../net01d/followup04/analysis/gz-simhealth-b1-01/RESULT.md)'],
        ['之前的两张网关/Wi-Fi对比图','[最早一对](../../net01d/followup04/analysis/comparison/coverage-and-gt-comparison.png) · [后续一对](../../net01d/followup04/analysis/comparison-b02/coverage-and-gt-comparison.png)']])
    text=f'''# ROS直接通信、本地网关与Wi-Fi：覆盖率、轨迹及结果汇总

本文把之前主要的Gazebo通信对比图表重新整理为中文。所有曲线、轨迹和数值都来自已有封存记录，本次没有新跑机器人、训练模型或改动评价标准。

**目前能直接看到：三种业务传输方式都已有机器人真实探索记录；接入ns-3以后仍能完成高覆盖探索。但探索时间有明显波动，不能仅凭某次Wi-Fi更快或更慢，就认定无线通信带来了相应比例的性能变化。**

这里分为两批：早期四种条件各一次，以及最近共同版本下网关/Wi-Fi各三次。另在附录保留一个早期退出异常回合。**这不是把全部历史实验混为一个同版本样本集**；早期数据不能充当最近版本缺少的ROS直取或受限Wi-Fi重复实验。

## 1. 四种通信方式分别是什么

{mapping}

本汇总的场景均为Corr6201走廊地图，3台TurtleBot3 Waffle，每个完整任务窗口180仿真秒。四种方式使用固定v1.1.0 PPO高层目标分配网络，路径规划、局部避障和速度控制由Nav2执行。Wi-Fi组不是给机器人换了另一种探索算法。联网条件下的关键探索业务不能通过直接DDS旁路；图中的真值背景和轨迹用于评价展示，不是PPO的直接输入。

## 2. 看图前需要统一的口径

- **覆盖率**：参考可达自由空间中，被地图正确观测为自由的比例；本场景评价分母为15,558格、38.895平方米。不是“地图里有颜色的格子比例”。
- **横轴**：从各回合原先记录的自主探索起点算起的Gazebo仿真秒数，不是电脑实际经过的秒数。起点已有约11%的初始扫描覆盖，并非从完全空白计时。
- **达到95%/98%的时间**：直接引用原分析中首次质量有效的阈值记录，不是本次看图重新取点。未达到应写“未达到”，不能写0。
- **最后覆盖率**：最后一个质量有效的收到地图样本。采样不一定恰好落在第180秒，曲线不强行补满或延伸。
- **叉号**：原记录中地图质量不合格的样本。它们原样保留，但不计入质量有效的阈值判定；阶梯曲线只连接有效样本。
- **路程**：机器人真实运动的采样累计距离，覆盖整个180秒任务窗口，不是只算到95%时刻，也不是规划路径长度。
- **结束原因**：下表完整任务窗口均由180秒预算结束；达到95%甚至99.9%，也不自动代表控制器已证明探索自然完成。
- **时间与安全配置**：这些结果属于已授权的共同模拟时间健康计龄实验；300毫秒按共同仿真时间计龄，另有真实时间进度保护。不能把它当成实机300毫秒安全性能已经验证。

## 3. 早期四种通信方式：各一次

这一批最接近原来的“四组对比图”。四个回合的停止、日志与异常记录代码存在版本差异，不是所有源码逐项完全相同的严格配对。这里保留原样，只作工程现象展示。

### 3.1 覆盖率随时间增长

![早期四种通信方式覆盖率](figures/01-早期四种通信方式-覆盖率.png)

{markdown_table(h_old,old_rows)}

ROS直接通信那次任务窗口内成功13个目标，另一个在收尾取消；控制器退出时报错，不能因覆盖率高而说整个回合正常结束。本地网关、高质量Wi-Fi及受限Wi-Fi在这里使用的是对应原报告中后续已正常收尾的回合。

这一次受限Wi-Fi比高质量Wi-Fi更早达到95%，是真实保留的结果，**不是已经证明弱网络更好**。收到地图和反馈的时刻会改变候选、目标选择和路线；一次任务时间还混合了运动执行、建图、计算及同步影响。

### 3.2 机器人真实轨迹与路程

![早期四种通信方式机器人轨迹](figures/02-早期四种通信方式-机器人轨迹.png)

{markdown_table(h_paths,old_paths)}

同一颜色始终代表同一机器人。空心圆是起点，方块是任务窗口最后位置；灰色为评价用场景障碍。路程不同说明实际分工与路线已经发生变化，不能把它们理解为同一条机器人路线只叠加了网络延迟。

## 4. 最近共同版本：网关与高质量Wi-Fi各重复三次

这批六个回合使用同一共同运行源码、同一固定PPO、场景、出生配置与已登记的种子。六次均完成180秒自主窗口、真实运动、停稳与正常进程收束。不过，固定种子不能消除ROS调度和实时联合仿真带来的执行差异；每次实际收到的初始地图、候选及后续路线并不完全一样。

### 4.1 六条覆盖率曲线

![最近六次重复覆盖率](figures/03-最近六次重复-覆盖率.png)

{markdown_table(h_new,new_rows)}

总计64个实际导航目标：62成功、2个导航中止；这里没有任务超时或取消。两次导航失败分别发生在第1轮Wi-Fi和第2轮网关，全部保留，没有只挑最快的回合。

### 4.2 三轮配对的机器人轨迹

![最近六次重复机器人轨迹](figures/04-最近六次重复-机器人轨迹.png)

{markdown_table(h_new_paths,new_paths)}

图中粗线特别标出从95%到98%覆盖之间的运动，便于看最后几个区域的探索代价。三角形是实际发送的目标，红叉是原Nav2中止的目标。目标来自估计共享地图，背景来自评价真值；它们可能有坐标偏差，图中没有通过拟合、平移把差异藏起来。

### 4.3 平均值、分布与配对差值

下表时间均为仿真秒；只汇总本批六次，**不掺入第3节四个旧回合**。

{markdown_table(h_stats,stats)}

{markdown_table(h_pairs,pairs)}

差值为负表示Wi-Fi本次较快，正表示Wi-Fi本次较慢。三轮Wi-Fi达到95%都较快；但第一轮达到98%反而慢38.90秒，平均达到98%的时间也略长。这说明“先达到95%”与“后续剩余区域探索更快”不是同一个结论。

此外，本地网关完成180仿真秒实际约需360秒，Wi-Fi约需408—420秒。Wi-Fi组仿真推进更慢，却不一定有更大的仿真T95。**电脑运行开销、模拟通信时间和机器人任务时间是三个不同概念，不能相互替代。**

只有单个走廊场景、每组3次，且不是三个独立无线种子。这里不作统计显著性、跨地图推广或通信优化收益声明。三机器人都有真实运动，但这些图也不能证明新增地图信息严格均匀地由三机贡献。

## 5. 之前量到的消息交付时间

以下数据来自**第3节早期四组**的原耗时导出，不是最近六次的网络测量。95分位数表示该组统计样本中约95%的阶段耗时不超过这个值，不是最大值。

|通信方式|机器人3健康消息发布完成→完整收件，95分位（真实毫秒）|同伴避让消息开始处理→被接受，95分位（真实毫秒）|
|---|---:|---:|
|ROS直接通信|3.314|9.121|
|本地网关|19.548|26.844|
|高质量Wi-Fi|102.312|133.443|
|受限Wi-Fi|125.250|165.935|

健康消息用于判断状态是否新鲜；同伴避让消息用于机器人间的安全空间约束。这里测的是指定业务链路的墙钟时间，包含相应的发布、排队、代理、联合仿真处理和接收开销，**不是纯无线电传播时间**，也不是地图或导航目标所有消息的统一时延。

另一个时间口径是ns-3内部已成功消费的健康/避让消息，从预定入网到完整重组的服务时间：

|早期条件|已匹配的成功消费消息数|95分位（模拟毫秒）|99分位（模拟毫秒）|最大值（模拟毫秒）|
|---|---:|---:|---:|---:|
|高质量Wi-Fi|10,799|17.317561|19.315920|23.582208|
|受限Wi-Fi|10,801|53.256243|60.688117|82.456931|

这个阶段包含TCP、队列、Wi-Fi竞争/重传和接收重组，不是单纯空口耗时；只统计已消费的匹配消息，**不能从这些计数算出全输入丢包率**。模拟毫秒不能与上表真实毫秒直接相加；不同阶段的95分位也不能相加。

这两张表支持一个有限事实：早期受限Wi-Fi的消息服务通常较慢；但它那个探索回合仍比高质量Wi-Fi更早达到95%。因此，任务时间与单项消息时延并不是简单的一一对应关系。

## 6. 保留的早期Wi-Fi退出异常回合

此前另一张网关/Wi-Fi图使用的是更早一次Wi-Fi回合。它达到95%用时65.43仿真秒、最后覆盖99.9164%，10个目标成功；但停后网关未能正常退出，最终被强制终止。第3节高质量Wi-Fi的65.84秒是另一次后续回合，不能将两者合并成一次成功记录。

![早期退出异常回合](figures/05-保留的早期退出异常回合.png)

这张附图中的本地网关就是第3节相同的本地网关回合，不另计一个样本。保留该图是为了说明历史过程问题没有被后续高覆盖或正常退出覆盖掉；它不加入最近三次重复的均值。

## 7. 这些结果现在能说明什么

1. **ns-3已接入实际探索业务路径。** 现有Wi-Fi回合并非只让网络仿真器独立产生吞吐量，机器人确有策略决策、Nav2执行、运动和地图增长记录；业务路径的证据仍以原报告为准。
2. **传输方式会与信息到达、目标分配和机器人路线共同发生变化。** 任务曲线已有差别，但目前不能把全部差别拆成“无线传播损失多少、网关处理多少、调度随机性多少”。
3. **同一模式的探索效率仍有明显波动。** 本地网关三次达到95%的时间从39.46到72.01秒；Wi-Fi从35.61到48.68秒。不能拿最好一次当平均水平。
4. **目前不能声称Wi-Fi提高了探索效率，也不能给出可信的固定无线性能损失百分比。** 研究价值在于已经有真实过网、任务和地图结果，而接下来的因果分解仍需要独立证据。

## 8. 原始来源、附件与复现

{sources}

中文图片在`figures/`，每张同时提供PNG和SVG；六份中文指标表在`data/`，可直接用表格软件打开。桌面副本使用相同相对目录，整文件夹复制后可阅读图文；本节指向仓库原件的链接和重绘脚本只在原仓库目录结构中有效。

绘图脚本为[make_summary.py](make_summary.py)，只读已有的覆盖率CSV、规范指标JSON、轨迹CSV和先前一次提取的事件缓存，不打开bag或大型网络原始账本，不运行ROS、Gazebo、ns-3、模型推理或训练。没有重算覆盖定义、首次有效阈值、导航终态或原安全判定。
'''
    (HERE/'通信方式对比图表汇总.md').write_text(text,encoding='utf-8')


def main():
    FIG.mkdir(exist_ok=True);DATA.mkdir(exist_ok=True)
    old=[load_old(mode,case) for mode,case in SPECS]
    new=json.loads((NEW/'SUMMARY.json').read_text())['rows']
    backgrounds=[]
    for reference in [OLD/'analysis/gz-simhealth-a1-03/metrics/reference-and-final.npz',
                      NEW/'gz-analysis'/new[0]['case']/'metrics/reference-and-final.npz']:
        with np.load(reference,allow_pickle=False) as ref:
            obstacles=ref['physical_obstacles'].astype(bool);origin=ref['origin'];res=float(ref['resolution'])
        backgrounds.append((obstacles,[origin[0],origin[0]+obstacles.shape[1]*res,
                                      origin[1],origin[1]+obstacles.shape[0]*res]))
    failed=load_old('B','gz-simhealth-b1-01')
    cover_old(old);paths_old(old,backgrounds[0]);cover_new(new);paths_new(new,backgrounds[1])
    failed_history([old[1],failed],backgrounds[0])
    make_document(old,new,failed)
    print('Saved Chinese Markdown, five PNG/SVG figure pairs and six Chinese CSV tables; no new runtime.')


if __name__=='__main__':
    main()
