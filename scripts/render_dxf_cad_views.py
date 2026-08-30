#!/usr/bin/env python3
"""Render selected DXF model-space windows as colored report figures.

The project intentionally avoids requiring AutoCAD/LibreCAD for evidence figures.
This renderer parses the dominant DXF entities directly and uses matplotlib to
produce reproducible PNG/PDF output.  It is an evidence renderer, not a full CAD
engine: INSERT/HATCH/DIMENSION are not exploded.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle, Arc
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DXF_DIR = ROOT / "data" / "intermediate" / "dxf"
FIG_DIR = ROOT / "report" / "figures"
PDF_DIR = ROOT / "report" / "cad_render"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Noto Sans CJK SC", "Noto Sans CJK JP", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
    "axes.facecolor": "#fbfcfe",
})


@dataclass(frozen=True)
class View:
    key: str
    source: str
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    title: str
    max_text: int = 80
    mode: str = "engineering"


VIEWS = [
    View(
        "cad_antiscour",
        "01-赣江西支特大桥抗冲刷防护（水下不分散混凝土）.dxf",
        -50250, -47850, 59600, 61650,
        "抗冲刷防护 CAD 局部视图",
        90,
        "engineering",
    ),
    View(
        "cad_five_sections",
        "西支5断面100-100，0906.dxf",
        390600, 394700, 3188200, 3192350,
        "赣江西支五断面 CAD 视图",
        100,
        "sections",
    ),
    View(
        "cad_contours",
        "02赣江西支特大桥等值线图.dxf",
        -85, 280, -112, 95,
        "赣江西支桥位等值线 CAD 视图",
        70,
        "contours",
    ),
    View(
        "cad_bridge_plan",
        "西支成果.dxf",
        396700, 400050, 3187700, 3191000,
        "西支成果桥位 CAD 视图",
        80,
        "plan",
    ),
]


def recover_text(s: str) -> str:
    s = s.replace("\\P", " ").replace("\\~", " ")
    s = re.sub(r"\\[A-Za-z][^;]*;", "", s)
    s = re.sub(r"\{\\[^}]*\}", "", s)
    try:
        raw = s.encode("latin1")
        recovered = raw.decode("gb18030")
        if recovered:
            s = recovered
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    s = "".join(ch for ch in s if ord(ch) >= 32 and not 127 <= ord(ch) <= 159)
    return re.sub(r"\s+", " ", s).strip()


def iter_pairs(path: Path):
    with path.open("r", encoding="latin1", errors="replace", newline=None) as f:
        while True:
            a = f.readline()
            if not a:
                return
            b = f.readline()
            if not b:
                return
            try:
                code = int(a.strip())
            except ValueError:
                continue
            yield code, b.rstrip("\r\n")


def fval(fields, code, default=None):
    for c, v in fields:
        if c == code:
            try:
                return float(v)
            except ValueError:
                return default
    return default


def ival(fields, code, default=0):
    v = fval(fields, code, None)
    return int(v) if v is not None else default


def bbox_intersects(v: View, xs, ys):
    if not xs or not ys:
        return False
    return not (
        max(xs) < v.xmin or min(xs) > v.xmax or
        max(ys) < v.ymin or min(ys) > v.ymax
    )


def inside(v: View, x, y):
    return v.xmin <= x <= v.xmax and v.ymin <= y <= v.ymax


def parse_for_view(path: Path, view: View):
    lines = []
    polys = []
    circles = []
    arcs = []
    texts = []

    in_entities = False
    current_type = None
    fields = []
    active_poly = None

    def finalize_active_poly():
        nonlocal active_poly
        if active_poly and len(active_poly["pts"]) >= 2:
            pts = active_poly["pts"]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if bbox_intersects(view, xs, ys):
                polys.append({
                    "pts": pts,
                    "closed": active_poly["closed"],
                    "layer": active_poly.get("layer", ""),
                })
        active_poly = None

    def flush_entity():
        nonlocal current_type, fields, active_poly
        if not current_type or not in_entities:
            current_type = None
            fields = []
            return
        typ = current_type
        layer = next((v for c, v in fields if c == 8), "")
        if typ == "POLYLINE":
            finalize_active_poly()
            active_poly = {
                "pts": [],
                "closed": bool(ival(fields, 70, 0) & 1),
                "layer": layer,
            }
        elif typ == "VERTEX" and active_poly is not None:
            x, y = fval(fields, 10), fval(fields, 20)
            z = fval(fields, 30, 0.0)
            if x is not None and y is not None:
                active_poly["pts"].append((x, y, z if z is not None else 0.0))
        elif typ == "SEQEND":
            finalize_active_poly()
        elif typ == "LINE":
            x1, y1, x2, y2 = fval(fields, 10), fval(fields, 20), fval(fields, 11), fval(fields, 21)
            if None not in (x1, y1, x2, y2) and bbox_intersects(view, [x1, x2], [y1, y2]):
                lines.append((x1, y1, x2, y2, layer))
        elif typ == "LWPOLYLINE":
            pts = []
            pending_x = None
            pending_y = None
            for c, raw in fields:
                if c == 10:
                    try:
                        pending_x = float(raw)
                    except ValueError:
                        pending_x = None
                elif c == 20 and pending_x is not None:
                    try:
                        pending_y = float(raw)
                    except ValueError:
                        pending_y = None
                    if pending_y is not None:
                        pts.append((pending_x, pending_y, 0.0))
                    pending_x = None
            if len(pts) >= 2 and bbox_intersects(view, [p[0] for p in pts], [p[1] for p in pts]):
                polys.append({"pts": pts, "closed": bool(ival(fields, 70, 0) & 1), "layer": layer})
        elif typ == "CIRCLE":
            x, y, r = fval(fields, 10), fval(fields, 20), fval(fields, 40)
            if None not in (x, y, r) and bbox_intersects(view, [x-r, x+r], [y-r, y+r]):
                circles.append((x, y, r, layer))
        elif typ == "ARC":
            x, y, r = fval(fields, 10), fval(fields, 20), fval(fields, 40)
            a0, a1 = fval(fields, 50, 0.0), fval(fields, 51, 360.0)
            if None not in (x, y, r) and bbox_intersects(view, [x-r, x+r], [y-r, y+r]):
                arcs.append((x, y, r, a0, a1, layer))
        elif typ in ("TEXT", "MTEXT") and len(texts) < view.max_text:
            x, y = fval(fields, 10), fval(fields, 20)
            if x is not None and y is not None and inside(view, x, y):
                chunks = [val for c, val in fields if c in (1, 3)]
                txt = recover_text("".join(chunks))
                if txt:
                    if len(txt) > 42:
                        txt = txt[:39] + "…"
                    texts.append((x, y, txt, layer))
        current_type = None
        fields = []

    pairs = iter_pairs(path)
    for code, value in pairs:
        if code == 0 and value == "SECTION":
            flush_entity()
            try:
                c2, v2 = next(pairs)
            except StopIteration:
                break
            in_entities = c2 == 2 and v2 == "ENTITIES"
            continue
        if code == 0 and value == "ENDSEC":
            flush_entity()
            finalize_active_poly()
            in_entities = False
            continue
        if in_entities and code == 0:
            flush_entity()
            current_type = value
            fields = []
        elif in_entities and current_type:
            fields.append((code, value))
    flush_entity()
    finalize_active_poly()
    return lines, polys, circles, arcs, texts


def poly_color(view: View, poly, index: int, n: int):
    if view.mode == "contours":
        zs = np.asarray([p[2] for p in poly["pts"]], dtype=float)
        finite = zs[np.isfinite(zs)]
        if finite.size and np.ptp(finite) > 1e-9:
            z = float(np.nanmedian(finite))
            t = (z - np.nanmin(finite)) / max(np.ptp(finite), 1e-9)
        else:
            t = index / max(n - 1, 1)
        return plt.colormaps["viridis"](0.10 + 0.80 * t)
    if view.mode == "sections":
        return "#1677a8"
    if view.mode == "plan":
        return "#0f766e"
    return "#2563eb"


def render_view(view: View, primitives):
    lines, polys, circles, arcs, texts = primitives
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(13.5, 8.5), dpi=180)
    ax.set_xlim(view.xmin, view.xmax)
    ax.set_ylim(view.ymin, view.ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(view.title, fontsize=17, fontweight="bold", pad=14)

    if lines:
        segments = [[(x1, y1), (x2, y2)] for x1, y1, x2, y2, _ in lines]
        lc = LineCollection(segments, colors="#64748b", linewidths=0.55, alpha=0.82, zorder=2)
        ax.add_collection(lc)

    for idx, poly in enumerate(polys):
        pts = np.asarray([(p[0], p[1]) for p in poly["pts"]], dtype=float)
        if pts.shape[0] > 1800:
            step = max(1, pts.shape[0] // 1800)
            pts = pts[::step]
        color = poly_color(view, poly, idx, len(polys))
        lw = 0.75 if view.mode != "contours" else 0.65
        ax.plot(pts[:, 0], pts[:, 1], color=color, linewidth=lw, alpha=0.90, zorder=3)
        if poly["closed"] and pts.shape[0] >= 3:
            ax.plot([pts[-1,0], pts[0,0]], [pts[-1,1], pts[0,1]], color=color, linewidth=lw, alpha=0.90, zorder=3)

    for x, y, r, _ in circles:
        ax.add_patch(Circle((x, y), r, fill=False, edgecolor="#e67e22", linewidth=0.8, alpha=0.95, zorder=4))
    for x, y, r, a0, a1, _ in arcs:
        if a1 < a0:
            a1 += 360.0
        ax.add_patch(Arc((x, y), 2*r, 2*r, theta1=a0, theta2=a1,
                         edgecolor="#dc2626", linewidth=0.85, alpha=0.95, zorder=4))

    xrange = view.xmax - view.xmin
    yrange = view.ymax - view.ymin
    fs = 6.1 if view.mode != "contours" else 5.4
    for x, y, txt, _ in texts:
        ax.text(x, y, txt, fontsize=fs, color="#111827", zorder=6,
                bbox=dict(boxstyle="round,pad=0.10", facecolor="white", edgecolor="none", alpha=0.72))

    ax.grid(True, color="#dbe3ec", linewidth=0.5, alpha=0.55)
    ax.tick_params(labelsize=8, colors="#475569")
    for spine in ax.spines.values():
        spine.set_color("#94a3b8")
        spine.set_linewidth(0.8)

    legend_text = "灰：辅助直线   蓝/绿：主要折线   橙：圆形结构   红：圆弧结构"
    if view.mode == "contours":
        legend_text = "等值线采用连续色带区分；灰线为其他辅助实体"
    ax.text(0.01, 0.015, legend_text, transform=ax.transAxes, fontsize=8.5,
            color="#334155", va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.28", facecolor="#f8fafc", edgecolor="#cbd5e1", alpha=0.96))
    ax.text(0.99, 0.015, f"来源：{view.source} · DXF model-space 程序化渲染",
            transform=ax.transAxes, fontsize=7.5, color="#64748b", va="bottom", ha="right")

    fig.tight_layout(pad=1.0)
    png = FIG_DIR / f"{view.key}.png"
    pdf = PDF_DIR / f"{view.key}.pdf"
    fig.savefig(png, dpi=220, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return png, pdf


def main():
    for view in VIEWS:
        src = DXF_DIR / view.source
        if not src.exists():
            raise FileNotFoundError(src)
        primitives = parse_for_view(src, view)
        counts = [len(x) for x in primitives]
        png, pdf = render_view(view, primitives)
        print(f"{view.key}: lines={counts[0]} polys={counts[1]} circles={counts[2]} arcs={counts[3]} texts={counts[4]}")
        print(f"  -> {png.relative_to(ROOT)}")
        print(f"  -> {pdf.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
