#!/usr/bin/env python3
"""Render selected CAD/DXF model-space windows into report-ready PNGs.

This intentionally uses only the Python standard library plus the system XeLaTeX
and Poppler executables.  It is therefore reproducible in the project Linux
environment without AutoCAD/LibreCAD or third-party Python packages.

The renderer covers the entities that dominate the supplied drawings:
LINE, LWPOLYLINE, POLYLINE/VERTEX, CIRCLE, ARC and TEXT/MTEXT.  INSERT/HATCH/
DIMENSION are not exploded; the output is an evidence view, not a replacement
for the source CAD drawing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DXF_DIR = ROOT / "data" / "dxf"
OUT_DIR = ROOT / "report" / "cad_render"
FIG_DIR = ROOT / "report" / "figures"


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


VIEWS = [
    View(
        "cad_antiscour",
        "01-赣江西支特大桥抗冲刷防护（水下不分散混凝土）.dxf",
        -50250, -47850, 59600, 61650,
        "抗冲刷防护 CAD 局部视图",
        90,
    ),
    View(
        "cad_five_sections",
        "西支5断面100-100，0906.dxf",
        390600, 394700, 3188200, 3192350,
        "赣江西支五断面 CAD 视图",
        100,
    ),
    View(
        "cad_contours",
        "02赣江西支特大桥等值线图.dxf",
        -85, 280, -112, 95,
        "赣江西支桥位等值线 CAD 视图",
        70,
    ),
    View(
        "cad_bridge_plan",
        "xizhichengguo.dxf",
        396700, 400050, 3187700, 3191000,
        "西支成果桥位 CAD 视图",
        80,
    ),
]


def recover_text(s: str) -> str:
    """Best-effort recovery of GBK text that was decoded as latin-1."""
    s = s.replace("\\P", " ").replace("\\~", " ")
    s = re.sub(r"\\[A-Za-z][^;]*;", "", s)
    s = re.sub(r"\{\\[^}]*\}", "", s)
    try:
        raw = s.encode("latin1")
        s2 = raw.decode("gb18030")
        if s2:
            s = s2
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tex_escape(s: str) -> str:
    repl = {
        "\\": r"\textbackslash{}",
        "{": r"\{", "}": r"\}",
        "#": r"\#", "$": r"\$", "%": r"\%", "&": r"\&",
        "_": r"\_", "^": r"\textasciicircum{}", "~": r"\textasciitilde{}",
    }
    return "".join(repl.get(ch, ch) for ch in s)


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


def sval(fields, code, default=""):
    for c, v in fields:
        if c == code:
            return v
    return default


def bbox_intersects(v: View, xs, ys, pad=0.0):
    if not xs or not ys:
        return False
    return not (
        max(xs) < v.xmin - pad or min(xs) > v.xmax + pad or
        max(ys) < v.ymin - pad or min(ys) > v.ymax + pad
    )


def inside(v: View, x, y):
    return v.xmin <= x <= v.xmax and v.ymin <= y <= v.ymax


def parse_for_view(path: Path, view: View):
    lines = []
    polys = []
    circles = []
    arcs = []
    texts = []

    section = None
    in_entities = False
    current_type = None
    fields = []
    active_poly = None

    def finalize_active_poly():
        nonlocal active_poly
        if active_poly and len(active_poly["pts"]) >= 2:
            pts = active_poly["pts"]
            if bbox_intersects(view, [p[0] for p in pts], [p[1] for p in pts]):
                polys.append((pts, active_poly["closed"]))
        active_poly = None

    def flush_entity():
        nonlocal current_type, fields, active_poly
        if not current_type or not in_entities:
            current_type = None
            fields = []
            return
        typ = current_type
        if typ == "POLYLINE":
            finalize_active_poly()
            active_poly = {"pts": [], "closed": bool(ival(fields, 70, 0) & 1)}
        elif typ == "VERTEX" and active_poly is not None:
            x, y = fval(fields, 10), fval(fields, 20)
            if x is not None and y is not None:
                active_poly["pts"].append((x, y))
        elif typ == "SEQEND":
            finalize_active_poly()
        elif typ == "LINE":
            x1, y1, x2, y2 = fval(fields, 10), fval(fields, 20), fval(fields, 11), fval(fields, 21)
            if None not in (x1, y1, x2, y2) and bbox_intersects(view, [x1, x2], [y1, y2]):
                lines.append((x1, y1, x2, y2))
        elif typ == "LWPOLYLINE":
            pts = []
            pending_x = None
            for c, raw in fields:
                if c == 10:
                    try: pending_x = float(raw)
                    except ValueError: pending_x = None
                elif c == 20 and pending_x is not None:
                    try: pts.append((pending_x, float(raw)))
                    except ValueError: pass
                    pending_x = None
            if len(pts) >= 2 and bbox_intersects(view, [p[0] for p in pts], [p[1] for p in pts]):
                polys.append((pts, bool(ival(fields, 70, 0) & 1)))
        elif typ == "CIRCLE":
            x, y, r = fval(fields, 10), fval(fields, 20), fval(fields, 40)
            if None not in (x, y, r) and bbox_intersects(view, [x-r, x+r], [y-r, y+r]):
                circles.append((x, y, r))
        elif typ == "ARC":
            x, y, r = fval(fields, 10), fval(fields, 20), fval(fields, 40)
            a0, a1 = fval(fields, 50, 0.0), fval(fields, 51, 360.0)
            if None not in (x, y, r) and bbox_intersects(view, [x-r, x+r], [y-r, y+r]):
                arcs.append((x, y, r, a0, a1))
        elif typ in ("TEXT", "MTEXT") and len(texts) < view.max_text:
            x, y = fval(fields, 10), fval(fields, 20)
            if x is not None and y is not None and inside(view, x, y):
                chunks = [val for c, val in fields if c in (1, 3)]
                txt = recover_text("".join(chunks))
                if txt:
                    if len(txt) > 48:
                        txt = txt[:45] + "…"
                    texts.append((x, y, txt))
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
            section = v2 if c2 == 2 else None
            in_entities = section == "ENTITIES"
            continue
        if code == 0 and value == "ENDSEC":
            flush_entity()
            finalize_active_poly()
            section = None
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


def transform(view: View):
    max_w, max_h = 24.0, 15.0
    sx = max_w / (view.xmax - view.xmin)
    sy = max_h / (view.ymax - view.ymin)
    s = min(sx, sy)
    draw_w = (view.xmax - view.xmin) * s
    draw_h = (view.ymax - view.ymin) * s
    ox = (max_w - draw_w) / 2.0
    oy = (max_h - draw_h) / 2.0

    def xy(x, y):
        return ox + (x - view.xmin) * s, oy + (y - view.ymin) * s
    return xy, s


def render_tex(view: View, primitives):
    lines, polys, circles, arcs, texts = primitives
    xy, scale = transform(view)
    out = OUT_DIR / f"{view.key}.tex"
    source = tex_escape(view.source)
    title = tex_escape(view.title)
    cmds = []
    cmds.append(r"\documentclass[UTF8]{ctexart}")
    cmds.append(r"\usepackage[paperwidth=27cm,paperheight=19cm,margin=1cm]{geometry}")
    cmds.append(r"\usepackage{tikz}")
    cmds.append(r"\usepackage{xcolor}")
    cmds.append(r"\pagestyle{empty}")
    cmds.append(r"\setlength{\parindent}{0pt}")
    cmds.append(r"\begin{document}")
    cmds.append(r"\begin{center}")
    cmds.append(rf"{{\Large\bfseries {title}}}\\[2mm]")
    cmds.append(r"\begin{tikzpicture}[line cap=round,line join=round]")
    cmds.append(r"\path[use as bounding box] (0,0) rectangle (24,15);")
    cmds.append(r"\draw[line width=0.35pt] (0,0) rectangle (24,15);")
    cmds.append(r"\begin{scope}")
    cmds.append(r"\clip (0,0) rectangle (24,15);")
    for x1, y1, x2, y2 in lines:
        a, b = xy(x1, y1), xy(x2, y2)
        cmds.append(rf"\draw[line width=0.13pt] ({a[0]:.4f},{a[1]:.4f}) -- ({b[0]:.4f},{b[1]:.4f});")
    for pts, closed in polys:
        q = [xy(x, y) for x, y in pts]
        if len(q) > 1200:
            q = q[::max(1, len(q)//1200)]
        path = " -- ".join(f"({x:.4f},{y:.4f})" for x, y in q)
        if closed:
            path += " -- cycle"
        cmds.append(rf"\draw[line width=0.13pt] {path};")
    for x, y, r in circles:
        c = xy(x, y)
        cmds.append(rf"\draw[line width=0.13pt] ({c[0]:.4f},{c[1]:.4f}) circle ({r*scale:.4f});")
    for x, y, r, a0, a1 in arcs:
        if a1 < a0:
            a1 += 360.0
        p0 = xy(x + r*math.cos(math.radians(a0)), y + r*math.sin(math.radians(a0)))
        rr = r * scale
        cmds.append(rf"\draw[line width=0.13pt] ({p0[0]:.4f},{p0[1]:.4f}) arc[start angle={a0:.3f},end angle={a1:.3f},radius={rr:.4f}];")
    for x, y, txt in texts:
        p = xy(x, y)
        cmds.append(rf"\node[anchor=west,scale=0.32,fill=white,inner sep=0.3pt] at ({p[0]:.4f},{p[1]:.4f}) {{{tex_escape(txt)}}};")
    cmds.append(r"\end{scope}")
    cmds.append(r"\end{tikzpicture}\\[1mm]")
    cmds.append(rf"{{\footnotesize 来源：\texttt{{{source}}}；DXF model-space 程序化渲染。}}")
    cmds.append(r"\end{center}")
    cmds.append(r"\end{document}")
    out.write_text("\n".join(cmds) + "\n", encoding="utf-8")
    return out


def compile_view(tex_path: Path, view: View):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
        cwd=OUT_DIR, check=True, stdout=subprocess.DEVNULL,
    )
    pdf = OUT_DIR / f"{view.key}.pdf"
    png_prefix = FIG_DIR / view.key
    subprocess.run(
        ["pdftoppm", "-singlefile", "-png", "-r", "180", str(pdf), str(png_prefix)],
        check=True, stdout=subprocess.DEVNULL,
    )
    return pdf, png_prefix.with_suffix(".png")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for view in VIEWS:
        src = DXF_DIR / view.source
        if not src.exists():
            raise FileNotFoundError(src)
        primitives = parse_for_view(src, view)
        counts = [len(x) for x in primitives]
        tex = render_tex(view, primitives)
        pdf, png = compile_view(tex, view)
        print(f"{view.key}: lines={counts[0]} polys={counts[1]} circles={counts[2]} arcs={counts[3]} texts={counts[4]}")
        print(f"  -> {pdf.relative_to(ROOT)}")
        print(f"  -> {png.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
