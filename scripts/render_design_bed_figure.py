#!/usr/bin/env python3
"""Render current bed versus the CAD01-direct construction-period design bed."""

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "report" / "data"
FIG = ROOT / "report" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Noto Sans CJK SC", "Noto Sans CJK JP", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.facecolor": "white",
        "axes.facecolor": "#fbfcfe",
    }
)


def load_xy(name: str) -> tuple[np.ndarray, np.ndarray]:
    values = np.loadtxt(DATA / name, skiprows=1)
    return values[:, 0], values[:, 1]


def main() -> None:
    current_x, current_z = load_xy("current_section.dat")
    design_x, design_z = load_xy("design_cad01_section.dat")
    controls = np.loadtxt(DATA / "design_controls.dat", skiprows=1)

    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=180)
    ax.plot(current_x, current_z, color="#374151", linewidth=2.4, label="现状桥下断面", zorder=4)
    ax.plot(
        design_x,
        design_z,
        color="#dc2626",
        linewidth=2.5,
        label="CAD 01：中地面线（建设期）",
        zorder=6,
    )

    design_on_current = np.interp(current_x, design_x, design_z)
    ax.fill_between(
        current_x,
        current_z,
        design_on_current,
        where=design_on_current >= current_z,
        color="#f59e0b",
        alpha=0.13,
        interpolate=True,
        label="设计线高于现状",
        zorder=2,
    )
    ax.fill_between(
        current_x,
        current_z,
        design_on_current,
        where=design_on_current < current_z,
        color="#0ea5e9",
        alpha=0.10,
        interpolate=True,
        label="设计线低于现状",
        zorder=2,
    )

    piers = controls[:, 0].astype(int)
    stations = controls[:, 1]
    elevations = controls[:, 2]
    ax.scatter(
        stations,
        elevations,
        s=92,
        marker="o",
        color="#7c3aed",
        edgecolor="white",
        linewidth=1.4,
        label="CAD 表值交叉核验点",
        zorder=8,
    )
    for pier, station, elevation in zip(piers, stations, elevations):
        ax.annotate(
            f"{pier}#  Z={elevation:.2f} m",
            xy=(station, elevation),
            xytext=(0, 16),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9.2,
            color="#5b21b6",
            arrowprops=dict(arrowstyle="-", color="#8b5cf6", linewidth=0.9),
            bbox=dict(
                boxstyle="round,pad=0.22",
                facecolor="white",
                edgecolor="#ddd6fe",
                alpha=0.96,
            ),
        )

    ax.axhline(22.190, color="#0891b2", linewidth=1.5, linestyle=":", zorder=1)
    ax.text(
        515,
        22.42,
        "面积核对水位 WSE = 22.190 m",
        ha="right",
        va="bottom",
        fontsize=9.2,
        color="#0e7490",
    )

    ax.set_xlim(0, 535)
    ax.set_ylim(-2, 30)
    ax.set_xlabel("断面 station (m)", fontsize=11)
    ax.set_ylabel("高程 (m)", fontsize=11)
    ax.set_title("桥下断面：现状河床与 CAD 01 直接设计河床", fontsize=16, fontweight="bold", pad=12)
    ax.grid(True, color="#dbe3ec", linewidth=0.65, alpha=0.72)
    ax.tick_params(labelsize=9.5, colors="#475569")
    for spine in ax.spines.values():
        spine.set_color("#94a3b8")

    ax.legend(
        loc="lower right",
        fontsize=9.0,
        frameon=True,
        framealpha=0.96,
        facecolor="white",
        edgecolor="#cbd5e1",
    )

    note = (
        "来源：CAD 01 中“中地面线（建设期）”标签 → 引线 → 完整折线直接提取。\n"
        "WSE=22.190 m：CAD 直接毛面积 5934.568 m²，净面积 5654.568 m²；"
        "表值 5980/5700 m²，差 45.432 m²（约 0.76%）。"
    )
    ax.text(
        0.012,
        0.018,
        note,
        transform=ax.transAxes,
        fontsize=8.8,
        color="#334155",
        va="bottom",
        ha="left",
        bbox=dict(
            boxstyle="round,pad=0.35",
            facecolor="#f8fafc",
            edgecolor="#cbd5e1",
            alpha=0.97,
        ),
    )

    fig.tight_layout(pad=1.1)
    png = FIG / "design_bed_cad01.png"
    pdf = FIG / "design_bed_cad01.pdf"
    fig.savefig(png, dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(png.relative_to(ROOT))
    print(pdf.relative_to(ROOT))


if __name__ == "__main__":
    main()
