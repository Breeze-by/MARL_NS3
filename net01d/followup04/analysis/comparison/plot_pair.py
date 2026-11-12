"""Plot only saved canonical exports and original GT CSV, no bag/runtime I/O."""
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "net01d/followup02/analysis"))
from plot_case_evidence import read_csv  # Existing Agg/NumPy/Matplotlib helper.
import matplotlib.pyplot as plt
import numpy as np


def main():
    base = REPO / "net01d/followup04"
    output = base / "analysis/comparison"
    arms = [("gz-simhealth-a1-03", "A1-03: local Gateway", "#1767a6", "-"),
            ("gz-simhealth-b1-01", "B1: real ns-3 Wi-Fi TCP", "#c56a12", "--")]
    data = []
    for case, label, color, style in arms:
        analysis = base / "analysis" / case
        metrics = json.loads((analysis / "metrics/result.json").read_text())
        curve = read_csv(analysis / "metrics/coverage.csv")
        path = base / "runs" / case / "trajectories.csv"
        trajectory = [r for r in read_csv(path) if metrics["start_sim"] <= float(r["sim_s"]) <= metrics["end_sim"]]
        data.append(dict(case=case, label=label, color=color, style=style,
                         metrics=metrics, curve=curve, trajectory=trajectory))
    reference = base / "analysis/gz-simhealth-a1-03/metrics/reference-and-final.npz"
    with np.load(reference, allow_pickle=False) as ref:
        obstacles = ref["physical_obstacles"]; origin = ref["origin"]; resolution = float(ref["resolution"])
    extent = [origin[0], origin[0] + obstacles.shape[1] * resolution,
              origin[1], origin[1] + obstacles.shape[0] * resolution]
    xs = [float(r["x"]) for arm in data for r in arm["trajectory"]]
    ys = [float(r["y"]) for arm in data for r in arm["trajectory"]]
    limits = (min(xs) - .85, max(xs) + .85, min(ys) - .85, max(ys) + .85)
    plt.rcParams.update({"font.size": 11, "svg.fonttype": "none",
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 3, figsize=(18.2, 7.0),
        gridspec_kw={"width_ratios": [1.35, 1, 1]})
    ax = axes[0]
    for arm in data:
        m = arm["metrics"]; curve = arm["curve"]
        ax.step([float(r["elapsed_sim_s"]) for r in curve], [100 * float(r["coverage"]) for r in curve],
            where="post", color=arm["color"], linestyle=arm["style"], linewidth=2.3,
            label=f'{arm["label"]} ({100*m["final_coverage"]:.4f}%)')
        bad = [r for r in curve if r["map_quality_valid"] != "True"]
        ax.scatter([float(r["elapsed_sim_s"]) for r in bad], [100 * float(r["coverage"]) for r in bad],
            marker="x", color=arm["color"], s=27, linewidths=1.2, zorder=5)
        t95 = m["quality_valid_thresholds"]["0.95"]["elapsed_sim_s"]
        ax.scatter([t95], [95], marker="*", color=arm["color"], s=135, edgecolors="white", linewidths=.5, zorder=6)
        textxy = (5, 72) if arm is data[0] else (86, 64)
        ax.annotate(f'{"A1" if arm is data[0] else "B"} T95 = {t95:.2f} sim s', xy=(t95, 95),
            xytext=textxy, color=arm["color"], fontsize=11,
            arrowprops=dict(arrowstyle="->", color=arm["color"], lw=1.1))
    for threshold, dash in [(90, "--"), (95, ":")]:
        ax.axhline(threshold, color="#6b7280", linestyle=dash, linewidth=.9, alpha=.75)
        ax.text(179, threshold - 2.5, f"{threshold}%", ha="right", color="#59616e", fontsize=9)
    ax.set(title="R primary coverage | original ROI: 15,558 cells",
        xlabel="Simulation time since original phase start (s)", ylabel="Correct free-space coverage (%)",
        xlim=(0, 180), ylim=(0, 102))
    ax.grid(alpha=.18); ax.legend(loc="lower right", fontsize=9.5, framealpha=.95)
    ax.text(.03, .28, "T90  A1: 35.85 s   B: 63.27 s", transform=ax.transAxes,
        fontsize=10, bbox=dict(facecolor="white", edgecolor="#d1d5db", alpha=.9))
    counts = {}
    for ax, arm in zip(axes[1:], data):
        m = arm["metrics"]
        ax.imshow(obstacles, origin="lower", extent=extent, cmap="Greys", vmin=0, vmax=1, alpha=.55)
        counts[arm["case"]] = {}
        for robot, color in zip(("tb1", "tb2", "tb3"), ("#1767a6", "#d97706", "#178653")):
            rows = [r for r in arm["trajectory"] if r["robot"] == robot]
            counts[arm["case"]][robot] = len(rows)
            x, y = [float(r["x"]) for r in rows], [float(r["y"]) for r in rows]
            length = m["robot_metrics"][robot]["path_m"]
            ax.plot(x, y, color=color, linewidth=1.7, label=f"{robot}: {length:.2f} m")
            ax.scatter(x[0], y[0], facecolors="white", edgecolors=color, marker="o", s=32, zorder=4)
            ax.scatter(x[-1], y[-1], color=color, marker="s", s=27, zorder=4)
        ax.set(title=arm["label"] + "\nGazebo GT trajectories (diagnostic)",
            xlabel="World x (m)", ylabel="World y (m)", aspect="equal",
            xlim=limits[:2], ylim=limits[2:])
        ax.grid(alpha=.15); ax.legend(loc="lower left", fontsize=9.5, framealpha=.95)
    fig.suptitle("Same source 2be7 | local A1 vs real Wi-Fi B | one 180-sim-s run per arm", fontsize=16, y=.965)
    fig.text(.055, .875, "A1: 180 sim complete; host/closure gates passed", color="#1767a6", fontsize=11)
    fig.text(.515, .875, "B: 180 sim business complete; host/network exit FAIL (Gateway -9)", color="#b42318", fontsize=11)
    fig.text(.045, .115, "x: original quality-invalid samples. Valid samples: A1 169/175; B 240/247. T95 uses unchanged quality-valid thresholds.", fontsize=9.5)
    fig.text(.045, .080, "Open circle: first GT sample; square: last. Curves and paths stop at original phase samples; no padded endpoints or post-stop maps.", fontsize=9.5)
    fig.text(.045, .045, "Only A1-03/B1 shown; earlier A1-01/02 failures retained, not mapped to zero coverage. Different trajectories; this single pair does not isolate pure RF causality.", fontsize=9.5)
    fig.subplots_adjust(left=.045, right=.985, bottom=.22, top=.80, wspace=.28)
    files = []
    for suffix in ("png", "svg"):
        target = output / f"coverage-and-gt-comparison.{suffix}"
        fig.savefig(target, dpi=180, facecolor="white"); files.append(str(target))
    plt.close(fig)
    manifest = dict(source="Saved canonical exports + original GT CSV only", runtime="2be7e229492d29817057fa8db166e38f114ca209",
        files=files, reference_background=str(reference), background_scope="Common physical-obstacle display; no metric recomputation",
        arms=[dict(case=a["case"], label=a["label"], start_sim=a["metrics"]["start_sim"], end_sim=a["metrics"]["end_sim"],
            coverage_source=str(base/"analysis"/a["case"]/"metrics/coverage.csv"),
            metrics_source=str(base/"analysis"/a["case"]/"metrics/result.json"),
            trajectory_source=str(base/"runs"/a["case"]/"trajectories.csv")) for a in data],
        plotted_trajectory_counts=counts, B_integrity="Business180complete; host/networkexitFAIL", no_padded_endpoints=True,
        original_phase_quality_thresholds_unchanged=True, bag_reads=0, Gateway_reads=0, native_reads=0, new_models=0, Torch_imports=0)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__": main()
