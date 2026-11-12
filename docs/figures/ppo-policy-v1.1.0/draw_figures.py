"""Source-faithful scientific diagrams; rendering only, no policy execution."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle
from matplotlib import font_manager
import numpy as np

OUT = Path(__file__).resolve().parent
FONT = font_manager.FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams.update({'font.family': FONT.get_name(), 'font.size': 11,
                     'svg.fonttype': 'none', 'pdf.fonttype': 3,
                     'axes.unicode_minus': False, 'mathtext.fontset': 'dejavusans'})
INK = '#243449'
BLUE = '#3B72A3'
GREEN = '#38866C'
PURPLE = '#8062A1'
ORANGE = '#B97A30'
GRAY = '#677889'
PALE = {'blue': '#ECF3F9', 'green': '#ECF5EF', 'purple': '#F3EFF8',
        'orange': '#FBF3E8', 'gray': '#F4F6F8'}


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w*.82, h*.82))
    fig.patch.set_facecolor('white')
    fig.subplots_adjust(left=.015, right=.985, bottom=.02, top=.98)
    ax.set(xlim=(0, w), ylim=(0, h))
    ax.axis('off')
    return fig, ax


def text(ax, x, y, s, size=11, color=INK, ha='center', weight='normal', va='center', **kw):
    for source, math_label in {
        'sₜ₊₁': r'$s_{t+1}$', 'sₜ': r'$s_t$', 'xₜ': r'$x_t$', 'rₜ': r'$r_t$',
        'δₜ': r'$\delta_t$', 'Âₜ': r'$\hat A_t$', 'R̂ₜ': r'$\hat R_t$', 'R̂': r'$\hat R$',
        'a₁': r'$a_1$', 'a₂': r'$a_2$', 'a₃': r'$a_3$',
        'π₁': r'$\pi_1$', 'π₂': r'$\pi_2$', 'π₃': r'$\pi_3$',
        'm₁': r'$m_1$', 'm₂': r'$m_2$', 'm₃': r'$m_3$',
        'Σᵢ': r'$\sum_i$', 'πᵢ': r'$\pi_i$', 'Hᵢ': r'$H_i$',
        'ℝ⁷⁰¹': r'$\mathbb{R}^{701}$', '10⁻⁴': r'$10^{-4}$', '⋮': r'$\vdots$',
    }.items():
        s = s.replace(source, math_label)
    return ax.text(x, y, s, fontsize=size, color=color, ha=ha, va=va,
                   fontweight=weight, linespacing=1.5, **kw)


def box(ax, x, y, w, h, title, body='', color=BLUE, fill='blue', size=11, body_size=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.035,rounding_size=0.07',
                              linewidth=1.1, edgecolor=color, facecolor=PALE[fill], zorder=2))
    if body:
        text(ax, x+w/2, y+h-.32, title, size=size, color=color, weight='bold')
        text(ax, x+w/2, y+(h-.56)/2, body, size=body_size)
    else:
        text(ax, x+w/2, y+h/2, title, size=size, color=color)


def arrow(ax, points, color=GRAY, dash=False, lw=1.35, head=11):
    if len(points)>2:
        ax.plot(*zip(*points[:-1]), color=color, lw=lw, ls='--' if dash else '-', zorder=1)
    ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle='-|>', mutation_scale=head,
                                lw=lw, color=color, linestyle='--' if dash else '-', zorder=1))


def section(ax, x, y, label):
    text(ax, x, y, label, size=14, ha='left', weight='bold')


def save(fig, name):
    for ext in ('svg', 'pdf', 'png'):
        fig.savefig(OUT/f'{name}.{ext}', dpi=300, facecolor='white')
    plt.close(fig)


def neural_column(ax, x, ys, color):
    for y in ys:
        ax.add_patch(Circle((x, y), .13, facecolor=PALE['blue'], edgecolor=color, lw=1.3, zorder=3))
    text(ax, x, (ys[2]+ys[3])/2, '⋮', size=19, color=color)


def architecture():
    fig, ax = canvas(24, 13.2)
    text(ax, 12, 12.67, '三机器人中央 PPO：实际网络结构与目标输出', size=21, weight='bold')
    text(ax, 12, 12.10, 'MR3-RL-POLICY-v1.1.0  ·  checkpoint-00512.pt  ·  共享 MLP + Actor / Critic', size=11, color=GRAY)
    section(ax, .35, 11.32, '(a) 观察编码  Observation encoding')
    section(ax, 6.65, 11.32, '(b) 可学习网络  Actor–Critic')
    section(ax, 16.05, 11.32, '(c) 规则约束与目标执行')
    ax.plot([6.3, 6.3], [3.2, 11.0], color='#DCE2E8', lw=1)
    ax.plot([15.65, 15.65], [3.2, 11.0], color='#DCE2E8', lw=1)

    box(ax, .4, 8.65, 4.6, 1.82, '共享占据地图  →  512 维',
        '固定 ROI、0.05 m 投影\n已知 / 占据两通道\n16 × 16 × 2 区块面积比例', body_size=11)
    box(ax, .4, 6.15, 4.6, 1.82, '三机器人状态  →  39 维',
        'tb1 → tb2 → tb3，固定顺序\n位置、朝向、速度、任务状态\n相对目标、任务持续时间：3 × 13', color=GREEN, fill='green', body_size=11)
    box(ax, .4, 3.65, 4.6, 1.82, '候选目标特征  →  150 维',
        '最多 15 个；每机最多 5 个\n位置、路径代价、信息增益等\n15 × 10；缺少的候选补零', color=ORANGE, fill='orange', body_size=11)
    ax.add_patch(Rectangle((5.35, 4.4), .57, 5.27, facecolor=PALE['gray'], edgecolor=GRAY, lw=1))
    text(ax, 5.635, 7.04, '拼\n接', size=13, color=GRAY)
    for y in (9.56, 7.06, 4.56):
        arrow(ax, [(5.05, y), (5.34, y)])
    text(ax, 5.63, 3.75, '701 维', size=12, weight='bold')
    arrow(ax, [(5.94, 7.05), (7.15, 7.05)])

    # Schematic neuron counts only. Explicit dimensions give actual layer sizes.
    ys = [9.3, 8.75, 8.2, 6.95, 6.4, 5.85]
    xs = [7.35, 9.25, 11.15]
    for left, right in zip(xs, xs[1:]):
        for ya in ys:
            for yb in ys:
                ax.plot([left, right], [ya, yb], color='#CCD6E0', lw=.55, alpha=.8, zorder=0)
    for x in xs:
        neural_column(ax, x, ys, BLUE)
    text(ax, 7.35, 10.18, '输入 [B, 701]', size=12)
    text(ax, 9.25, 10.18, '隐藏层 1', size=12)
    text(ax, 11.15, 10.18, '隐藏层 2', size=12)
    text(ax, 7.35, 5.2, '701', size=15, color=BLUE, weight='bold')
    text(ax, 9.25, 5.2, '128', size=15, color=BLUE, weight='bold')
    text(ax, 11.15, 5.2, '128', size=15, color=BLUE, weight='bold')
    text(ax, 8.30, 4.48, 'Linear(701, 128)\nTanh', size=10)
    text(ax, 10.23, 4.48, 'Linear(128, 128)\nTanh', size=10)
    text(ax, 9.25, 3.54, '两层共享全连接骨干；圆点为省略示意', size=10, color=GRAY)

    box(ax, 12.15, 8.03, 2.9, 2.55, 'Actor 目标评分头',
        'Linear(128, 51)\n[B, 51] → [B, 3, 17]', color=PURPLE, fill='purple', size=12, body_size=10)
    arrow(ax, [(11.3, 8.5), (12.12, 9.15)], color=PURPLE)
    # 51 positions are logits, not a probability illustration or measured data.
    for i in range(3):
        for j in range(17):
            ax.add_patch(Rectangle((12.38+j*.14, 8.20+i*.14), .105, .085,
                                   facecolor=PURPLE, alpha=.55, lw=0, zorder=4))
    box(ax, 12.15, 4.75, 2.9, 1.75, 'Critic 状态价值头',
        'Linear(128, 1)\nV(s)：每个联合状态 1 个标量', color=GREEN, fill='green', size=12, body_size=10)
    arrow(ax, [(11.3, 6.35), (12.12, 5.65)], color=GREEN)
    text(ax, 13.6, 4.16, '价值用于训练；不决定部署目标', size=10, color=GREEN)

    text(ax, 19.82, 10.63, '原始 logits 不是速度，也不是目标坐标', size=11, color=PURPLE)
    arrow(ax, [(15.09, 9.7), (16.3, 9.7)], color=PURPLE)
    for i, y in enumerate((9.30, 7.72, 6.14), 1):
        body = 'mask(s) → argmax' if i == 1 else f'mask(s, a₁{", a₂" if i == 3 else ""}) → argmax'
        box(ax, 16.35, y-.38, 3.1, .98, f'tb{i}：17 槽评分', body,
            color=PURPLE, fill='purple', size=11, body_size=9)
        if i < 3:
            arrow(ax, [(17.9, y-.42), (17.9, y-.93)], color=PURPLE)
    text(ax, 17.9, 4.76, '顺序约束：tb1 → tb2 → tb3\n后续 mask 随已选目标变化\n三组 logits 只前向计算一次', size=10, color=GRAY)
    box(ax, 20.35, 7.75, 3.05, 1.5, '联合离散动作',
        '(a₁, a₂, a₃)\n每机 1 个选择', color=PURPLE, fill='purple', size=12, body_size=12)
    for y in (9.3, 7.72, 6.14):
        arrow(ax, [(19.5, y+.10), (19.9, y+.10), (19.9, 8.5), (20.30, 8.5)], color=PURPLE)
    box(ax, 20.35, 5.43, 3.05, 1.43, '目标解释与验收',
        '候选索引 → 共享图 (x, y)\n或 KEEP / WAIT', color=ORANGE, fill='orange', body_size=10)
    arrow(ax, [(21.88, 7.70), (21.88, 6.9)])
    box(ax, 20.35, 3.25, 3.05, 1.35, 'Nav2 执行',
        '坐标变换 → NavigateToPose\n路径规划、避障、底盘运动', color=GREEN, fill='green', body_size=10)
    arrow(ax, [(21.88, 5.38), (21.88, 4.65)])

    ax.plot([.4, 23.5], [2.9, 2.9], color='#DCE2E8', lw=1)
    box(ax, .4, 1.0, 7.05, 1.46, '输入分解',
        '512（地图）+ 39（机器人）+ 150（候选）= 701\nFloat32；固定比例缩放；无在线均值/方差更新', body_size=11)
    box(ax, 7.85, 1.0, 7.45, 1.46, '网络规模',
        '共享骨干 106,368 + Actor 6,579 + Critic 129\n总计 113,076 个参数；无 CNN / RNN / Attention', color=GREEN, fill='green', body_size=11)
    box(ax, 15.7, 1.0, 7.7, 1.46, '规则不等于神经网络',
        '15 个候选槽 + KEEP + WAIT = 每头 17 槽\n归属 / 可达性 / 冲突 / 最大参与约束在网络外计算', color=ORANGE, fill='orange', body_size=11)
    text(ax, 12, .35, '部署采用确定性 masked argmax；训练采用条件 Categorical 采样。地图来自已接收的观测，不向网络输入仿真真值。', size=10, color=GRAY)
    save(fig, '01-network-architecture')


def learning_process():
    fig, ax = canvas(24, 15.1)
    text(ax, 12, 14.58, '中央 PPO 的训练闭环与冻结策略部署', size=21, weight='bold')
    text(ax, 12, 14.02, '同一观察 / 动作合同；训练更新与 Gazebo 推理是两个阶段', size=11, color=GRAY)
    section(ax, .45, 13.26, '(a) 历史训练阶段：二维运动学 / LiDAR 训练后端，不是 Gazebo 在线训练')
    ax.add_patch(FancyBboxPatch((.3, 6.12), 23.35, 6.69, boxstyle='round,pad=.02,rounding_size=.1',
                              edgecolor='#D7E0E8', facecolor='#FAFBFC', lw=1, zorder=0))
    box(ax, .65, 10.1, 4.05, 2.0, '探索环境',
        '三机器人运动与感知\n更新已观测共享地图\n计算奖励、终止 / 截断', color=GREEN, fill='green', size=13, body_size=11)
    box(ax, 5.55, 10.1, 4.05, 2.0, '统一观察与合法集合',
        'sₜ → 编码 xₜ ∈ ℝ⁷⁰¹\n机器人状态 + 地图 + 候选\n网络外计算条件动作 mask', size=13, body_size=11)
    box(ax, 10.45, 10.1, 4.05, 2.0, '共享 Actor–Critic',
        '701 → 128 → 128\nActor：3 × 17 logits\nCritic：V(sₜ)', color=PURPLE, fill='purple', size=13, body_size=11)
    box(ax, 15.35, 10.1, 4.05, 2.0, '条件联合采样',
        'tb1 → tb2 → tb3\n按各自前缀构造 mask\nCategorical → (a₁, a₂, a₃)', color=PURPLE, fill='purple', size=13, body_size=11)
    for xa, xb in ((4.74, 5.5), (9.64, 10.4), (14.54, 15.3)):
        arrow(ax, [(xa, 11.08), (xb, 11.08)])
    arrow(ax, [(19.45, 11.1), (22.9, 11.1), (22.9, 12.5), (2.68, 12.5), (2.68, 12.14)], color=GREEN)
    text(ax, 13.6, 12.60, '合法高层目标 → 受约束导航近似执行 → 新状态 sₜ₊₁ 与奖励 rₜ', size=10, color=GREEN)

    box(ax, .65, 6.7, 5.3, 2.3, '奖励：观测进展与执行代价',
        '+ 0.1 × 新观测自由面积 [m²]\n− 0.005 × 时间 [s] − 0.01 × 路程 [m]\n− 0.01 × 重复观测面积 [m²]\n− 0.02 × 静止无进展时间 [s] + 2 × 首次完成',
        color=GREEN, fill='green', size=12, body_size=10)
    arrow(ax, [(2.68, 10.04), (2.68, 9.05)], color=GREEN)
    box(ax, 6.65, 6.7, 4.75, 2.3, 'On-policy rollout：256 步',
        'xₜ、联合动作、实际条件 masks\n旧联合 log-prob、V(sₜ)\nrₜ、V(sₜ₊₁)、terminated / truncated\n只用于本批 PPO 更新，不是 DQN 经验池', size=12, body_size=10)
    arrow(ax, [(17.4, 10.03), (17.4, 9.5), (9.05, 9.5), (9.05, 9.05)])
    arrow(ax, [(5.99, 7.85), (6.6, 7.85)], color=GREEN)
    box(ax, 12.1, 6.7, 4.6, 2.3, 'GAE 与价值目标',
        'γ = 0.99，λ = 0.95\nδₜ = rₜ + γ(1−d)V(sₜ₊₁) − V(sₜ)\n优势 Âₜ；回报目标 R̂ₜ = Âₜ + V(sₜ)\nd 为自然终止；截断保留 bootstrap', size=12, body_size=10)
    arrow(ax, [(11.44, 7.85), (12.05, 7.85)])
    box(ax, 17.4, 6.7, 5.6, 2.3, 'PPO 更新共享骨干与两个头',
        'Policy clipped loss + Value loss − Entropy\nminibatch 128；每批 4 epochs\nAdam，learning rate = 3 × 10⁻⁴\n梯度裁剪范数 0.5；保存 checkpoint', color=ORANGE, fill='orange', size=12, body_size=10)
    arrow(ax, [(16.74, 7.85), (17.35, 7.85)])
    arrow(ax, [(20.2, 9.03), (20.2, 9.24), (12.45, 9.24), (12.45, 10.05)], color=ORANGE, dash=True)
    text(ax, 20.3, 9.40, '反向传播 / 参数更新', size=9, color=ORANGE)

    box(ax, .65, 3.65, 11.2, 1.83, '联合动作概率：与实际采样时的前缀约束一致',
        'π(a | s) = π₁(a₁ | s, m₁) · π₂(a₂ | s, m₂(a₁)) · π₃(a₃ | s, m₃(a₁,a₂))\nlog π(a | s) = Σᵢ log πᵢ；更新时复用采样保存的条件 masks', color=PURPLE, fill='purple', size=12, body_size=11)
    box(ax, 12.4, 3.65, 10.6, 1.83, '实际优化目标',
        'Lactor = −E[min(ρÂ, clip(ρ, 0.8, 1.2)Â)]；ρ = exp(log πnew − log πold)\nLvalue = ½ E[(R̂ − V)²]；Ltotal = Lactor + 0.5 Lvalue − 0.01 E[Σᵢ Hᵢ]',
        color=ORANGE, fill='orange', size=12, body_size=10)
    text(ax, 12, 5.78, '以上为当前权重对应的 RL04 训练配置；最终采用验证选择的 checkpoint-00512.pt（继承已有受训权重后追加训练）。', size=10, color=GRAY)

    section(ax, .45, 3.05, '(b) 当前部署阶段：固定网络只推理，不更新参数')
    bottom = [(.65, 4.7, 'Gazebo 三机器人', 'LiDAR → SLAM / 状态\n真实 Nav2 反馈与地图变化', GREEN, 'green'),
              (6.05, 4.9, '信息交付与中央状态', '按实验条件直接 / Gateway / ns-3\n收到的数据 → 融合与候选 → 701 维', BLUE, 'blue'),
              (11.65, 4.8, '固定 PPO + 原合法性规则', 'eval / no_grad；确定性 argmax\n无 optimizer、无在线训练', PURPLE, 'purple'),
              (17.15, 5.85, '高层目标 → 三套 Nav2', '原目标验收 / TF / Action 所有权\n规划、局部避障与速度控制由 Nav2 负责', GREEN, 'green')]
    for x,w,title,body,c,f in bottom:
        box(ax, x, 1.02, w, 1.55, title, body, color=c, fill=f, size=12, body_size=10)
    for a,b in ((5.4, 6.0), (11.0,11.6), (16.5,17.1)):
        arrow(ax, [(a, 1.8), (b, 1.8)])
    arrow(ax, [(20.05, .99), (20.05, .48), (2.95, .48), (2.95, .98)], color=GREEN)
    text(ax, 12, .16, '联网条件下关键业务必须经过 ns-3；独立评价真值不进入 PPO。图示为软件结构与流程，不表示已证明 PPO 性能优于传统方法。', size=9, color=GRAY)
    save(fig, '02-training-and-deployment')


if __name__ == '__main__':
    architecture()
    learning_process()
    print('Rendered 2 figures as PNG, SVG and PDF; no inference, training, ROS or Gazebo execution.')
