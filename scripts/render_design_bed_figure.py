#!/usr/bin/env python3
"""Render the reconstructed design-bed alternatives for the report."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "report" / "data"
FIG = ROOT / "report" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Noto Sans CJK SC", "Noto Sans CJK JP", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
    "axes.facecolor": "#fbfcfe",
})


def load_xy(name, xcol=0, ycol=1):
    arr = np.loadtxt(DATA / name, skiprows=1)
    return arr[:, xcol], arr[:, ycol]


def main():
    x0, y0 = load_xy("current_section.dat")
    xc, yc = load_xy("design_center_section.dat")
    xl, yl = load_xy("design_local_section.dat")
    xd, yd = load_xy("design_distributed_section.dat")
    pc = np.loadtxt(DATA / "pier_controls.dat", skiprows=1)

    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=180)

    # Existing bed first, then three reconstruction alternatives.
    ax.plot(x0, y0, color="#374151", linewidth=2.5, label="现状桥下断面", zorder=4)
    ax.plot(xc, yc, color="#dc2626", linewidth=2.2, label="设计河床－中心方案", zorder=5)
    ax.plot(xl, yl, color="#2563eb", linewidth=2.0, linestyle="--", label="设计河床－局部型", zorder=5)
    ax.plot(xd, yd, color="#059669", linewidth=2.0, linestyle="-.", label="设计河床－分布型", zorder=5)

    # Make the geometric modification visible without obscuring the three lines.
    yc_on_current = np.interp(x0, xc, yc)
    ax.fill_between(
        x0, y0, yc_on_current,
        where=yc_on_current >= y0,
        color="#f59e0b", alpha=0.13,
        interpolate=True, label="中心方案相对现状抬高区", zorder=2,
    )

    stations = pc[:, 1]
    design_elev = pc[:, 2]
    ax.scatter(stations, design_elev, s=92, marker="o", color="#7c3aed",
               edgecolor="white", linewidth=1.4, label="15/16/17# 设计泥面控制点", zorder=8)
    for pier, sta, elev in zip(pc[:, 0].astype(int), stations, design_elev):
        ax.annotate(
            f"{pier}#  Z={elev:.2f} m",
            xy=(sta, elev), xytext=(0, 16), textcoords="offset points",
            ha="center", va="bottom", fontsize=9.2, color="#5b21b6",
            arrowprops=dict(arrowstyle="-", color="#8b5cf6", linewidth=0.9),
            bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#ddd6fe", alpha=0.96),
        )

    # Design water level used to impose the area constraint.
    ax.axhline(22.190, color="#0891b2", linewidth=1.5, linestyle=":", zorder=1)
    ax.text(477, 22.42, "面积约束水位 WSE = 22.190 m", ha="right", va="bottom",
            fontsize=9.2, color="#0e7490")

    ax.set_xlim(0, 480)
    ax.set_ylim(-2, 30)
    ax.set_xlabel("断面 station (m)", fontsize=11)
    ax.set_ylabel("高程 (m)", fontsize=11)
    ax.set_title("桥下断面：现状河床与三种设计河床重建方案", fontsize=16, fontweight="bold", pad=12)
    ax.grid(True, color="#dbe3ec", linewidth=0.65, alpha=0.72)
    ax.tick_params(labelsize=9.5, colors="#475569")
    for spine in ax.spines.values():
        spine.set_color("#94a3b8")

    ax.legend(loc="lower right", fontsize=9.2, frameon=True, framealpha=0.96,
              facecolor="white", edgecolor="#cbd5e1", ncol=1)

    note = (
        "共同约束：15/16/17# 设计泥面高程；不降低现状河床；\n"
        "WSE=22.190 m 时总面积 5980 m²，扣除 280 m² 等效阻水后净行洪面积 5700 m²。"
    )
    ax.text(0.012, 0.018, note, transform=ax.transAxes, fontsize=9.0, color="#334155",
            va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#f8fafc", edgecolor="#cbd5e1", alpha=0.97))

    fig.tight_layout(pad=1.1)
    png = FIG / "design_bed_schemes.png"
    pdf = FIG / "design_bed_schemes.pdf"
    fig.savefig(png, dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(png.relative_to(ROOT))
    print(pdf.relative_to(ROOT))


if __name__ == "__main__":
    main()
