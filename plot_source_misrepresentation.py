#!/usr/bin/env python3
"""Optional figure builder; requires matplotlib. Reads analysis outputs only."""
import argparse
import json
from pathlib import Path

from analyse_source_misrepresentation import ROOT, DEFAULT_OUTPUT, MODELS, NAMES, STRATEGIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=ROOT / DEFAULT_OUTPUT / "analysis_summary.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    data = json.loads(args.summary.read_text())
    output = args.output_dir or args.summary.parent
    output.mkdir(parents=True, exist_ok=True)
    index = {(r["model"], r["strategy"], r["metric"]): r for r in data["paired_contrasts"]}
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "svg.fonttype": "none", "pdf.fonttype": 42})
    fig, axes = plt.subplots(2, 1, figsize=(8.8, 5.8), sharex=True)
    definitions = [("consensus_mismatch_rate", "Consensus", "#0072B2", "o", .12),
                   ("either_judge_mismatch_rate", "Either judge", "#D55E00", "s", -.12)]
    for ax, model, title in zip(axes, MODELS, ["GPT-5.4 mini", "GPT-5.5"]):
        ax.axvline(0, color="#666666", linestyle="--", linewidth=1)
        for y, strategy in zip([2, 1, 0], STRATEGIES[1:]):
            for metric, label, colour, marker, offset in definitions:
                r = index[model, strategy, metric]
                x, lo, hi = (r[k] for k in ("difference_percentage_points", "ci95_lower_percentage_points", "ci95_upper_percentage_points"))
                ax.errorbar(x, y + offset, xerr=[[x - lo], [hi - x]], fmt=marker,
                            color=colour, ecolor=colour, markersize=6, capsize=3, linewidth=1.5)
        ax.set_yticks([2, 1, 0], [NAMES[s] for s in STRATEGIES[1:]])
        ax.set_ylim(-.5, 2.55)
        ax.set_title(title, loc="left", fontsize=12, fontweight="bold", pad=9)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0, pad=10)
        ax.grid(axis="x", alpha=.17)
        ax.set_axisbelow(True)
    axes[-1].set_xlim(-7, 2)
    axes[-1].set_xticks(range(-7, 3))
    axes[-1].set_xlabel("Paired change in citation mismatch (percentage points)", labelpad=10)
    legend = [Line2D([0], [0], color=c, marker=m, label=label, markersize=6) for _, label, c, m, _ in definitions]
    fig.legend(handles=legend, loc="upper right", bbox_to_anchor=(.97, .99), ncol=2, frameon=False, fontsize=10)
    fig.text(.52, .045, "Negative values favour the strategy over baseline", ha="center", fontsize=10)
    fig.text(.52, .014, "100 paired tasks per comparison; 75 source clusters; pointwise 95% cluster-bootstrap intervals", ha="center", fontsize=8.5, color="#444444")
    fig.subplots_adjust(left=.265, right=.97, top=.88, bottom=.19, hspace=.55)
    for extension in ("png", "svg", "pdf"):
        fig.savefig(output / f"source_misrepresentation_forest.{extension}", dpi=300, facecolor="white")
    plt.close(fig)
    print(f"Saved PNG, SVG and PDF figures in {output}")


if __name__ == "__main__":
    main()
