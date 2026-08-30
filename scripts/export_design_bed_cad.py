from __future__ import annotations
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
SRC=ROOT/"data/dxf/西支5断面100-100，0906.dxf"
CUR=ROOT/"data/processed/cross_sections/西支桥下.csv"
DB=ROOT/"data/processed/design_bed"
OUT=ROOT/"deliverables/cad/design_bed"
OUT.mkdir(parents=True,exist_ok=True)

VARIANTS={
 "center": ("中心方案", DB/"西支桥下_设计河床.csv", "DESIGN_CENTER", 1),
 "local": ("局部型", DB/"西支桥下_设计河床_局部型.csv", "DESIGN_LOCAL", 5),
 "distributed": ("分布型", DB/"西支桥下_设计河床_分布型.csv", "DESIGN_DISTRIBUTED", 3),
}
LAYERS={
 "CURRENT_BED":8,
 "DESIGN_CENTER":1,
 "DESIGN_LOCAL":5,
 "DESIGN_DISTRIBUTED":3,
 "PIER_CONTROL":6,
 "WSE_22_190":4,
 "ANNOTATION":7,
 "FRAME":8,
}

def read_csv(path):
 with path.open(encoding="utf-8-sig",newline="") as f:
  return list(csv.DictReader(f))

def pts(path, design=True):
 rows=read_csv(path)
 return [(float(r["station_m_raw_direction"]), float(r["elevation_m"])) for r in rows]

current=pts(CUR)
variants={k:pts(v[1]) for k,v in VARIANTS.items()}
controls=[(15,127.291583188,4.27),(16,233.855335041,5.40),(17,348.858419066,9.56)]
WSE=22.190

# original CAD mapping for the bridge section, derived by extraction audit
X0=391496.2307640212
Y0=3193335.313820825
SX=10.0
SY=10.0

def pair(c,v): return f"{c:>3}\n{v}\n"
def header_r2000(ext):
 xmin,ymin,xmax,ymax=ext
 s=""
 s+=pair(0,"SECTION")+pair(2,"HEADER")
 s+=pair(9,"$ACADVER")+pair(1,"AC1015")
 s+=pair(9,"$DWGCODEPAGE")+pair(3,"ANSI_936")
 s+=pair(9,"$INSUNITS")+pair(70,6)
 s+=pair(9,"$MEASUREMENT")+pair(70,1)
 s+=pair(9,"$EXTMIN")+pair(10,f"{xmin:.6f}")+pair(20,f"{ymin:.6f}")+pair(30,"0.0")
 s+=pair(9,"$EXTMAX")+pair(10,f"{xmax:.6f}")+pair(20,f"{ymax:.6f}")+pair(30,"0.0")
 s+=pair(0,"ENDSEC")
 return s

def tables():
 s=pair(0,"SECTION")+pair(2,"TABLES")
 s+=pair(0,"TABLE")+pair(2,"LTYPE")+pair(70,1)
 s+=pair(0,"LTYPE")+pair(2,"CONTINUOUS")+pair(70,0)+pair(3,"Solid line")+pair(72,65)+pair(73,0)+pair(40,"0.0")
 s+=pair(0,"ENDTAB")
 s+=pair(0,"TABLE")+pair(2,"LAYER")+pair(70,len(LAYERS))
 for name,color in LAYERS.items():
  s+=layer_record(name,color)
 s+=pair(0,"ENDTAB")+pair(0,"ENDSEC")
 return s

def layer_record(name,color):
 return pair(0,"LAYER")+pair(2,name)+pair(70,0)+pair(62,color)+pair(6,"CONTINUOUS")

def lwpoly(points,layer,color=None,width=0.0):
 s=pair(0,"LWPOLYLINE")+pair(100,"AcDbEntity")+pair(8,layer)
 if color is not None: s+=pair(62,color)
 s+=pair(100,"AcDbPolyline")+pair(90,len(points))+pair(70,0)
 if width: s+=pair(43,f"{width:.4f}")
 for x,y in points:
  s+=pair(10,f"{x:.9f}")+pair(20,f"{y:.9f}")
 return s

def line(x1,y1,x2,y2,layer,color=None):
 s=pair(0,"LINE")+pair(100,"AcDbEntity")+pair(8,layer)
 if color is not None: s+=pair(62,color)
 s+=pair(100,"AcDbLine")+pair(10,f"{x1:.9f}")+pair(20,f"{y1:.9f}")+pair(30,"0")+pair(11,f"{x2:.9f}")+pair(21,f"{y2:.9f}")+pair(31,"0")
 return s

def circle(x,y,r,layer,color=None):
 s=pair(0,"CIRCLE")+pair(100,"AcDbEntity")+pair(8,layer)
 if color is not None: s+=pair(62,color)
 s+=pair(100,"AcDbCircle")+pair(10,f"{x:.9f}")+pair(20,f"{y:.9f}")+pair(30,"0")+pair(40,f"{r:.6f}")
 return s

def text(x,y,h,value,layer="ANNOTATION",color=None,rot=0):
 s=pair(0,"TEXT")+pair(100,"AcDbEntity")+pair(8,layer)
 if color is not None: s+=pair(62,color)
 s+=pair(100,"AcDbText")+pair(10,f"{x:.9f}")+pair(20,f"{y:.9f}")+pair(30,"0")+pair(40,f"{h:.6f}")+pair(1,value)+pair(50,f"{rot:.6f}")+pair(100,"AcDbText")
 return s

def standalone(include_keys,name):
 xs=[p[0] for p in current]; ys=[p[1] for p in current]
 ext=(min(xs)-18,min(ys)-8,max(xs)+18,max(max(ys),WSE)+18)
 s=header_r2000(ext)+tables()+pair(0,"SECTION")+pair(2,"ENTITIES")
 s+=lwpoly(current,"CURRENT_BED",8)
 for k in include_keys:
  cn,path,layer_name,color=VARIANTS[k]
  s+=lwpoly(variants[k],layer_name,color)
 s+=line(0,WSE,max(xs),WSE,"WSE_22_190",4)
 for pier,sta,elev in controls:
  s+=circle(sta,elev,2.2,"PIER_CONTROL",6)
  s+=text(sta+3,elev+1.2,3.2,f"{pier}# Z={elev:.2f}m","ANNOTATION",6)
 s+=text(0,max(max(ys),WSE)+10,5.0,"赣江西支特大桥 桥下设计河床断面","ANNOTATION",7)
 s+=text(0,max(max(ys),WSE)+4.5,3.0,"横纵坐标单位:m；设计线为本项目约束重建成果，非原设计院完整设计河床线。","ANNOTATION",7)
 s+=text(max(xs)-105,WSE+1.4,3.0,"WSE=22.190m","ANNOTATION",4)
 s+=pair(0,"ENDSEC")+pair(0,"EOF")
 path=OUT/name
 path.write_bytes(s.encode("gb18030",errors="replace"))
 return path

# Create standalone editable profile drawings.
standalone(["center","local","distributed"],"赣江西支桥下_设计河床_三方案对比_R2000.dxf")
for key,(cn,_,_,_) in VARIANTS.items():
 standalone([key],f"赣江西支桥下_设计河床_{cn}_R2000.dxf")

# Overlay design geometries into the original five-section DXF coordinates.
def entity_pairs_from_string(s):
    ls=s.splitlines(); out=[]
    for i in range(0,len(ls)-1,2): out.append([int(ls[i].strip()),ls[i+1]])
    return out

def world(points):
    return [(X0+x*SX,Y0+y*SY) for x,y in points]

def build_overlay(include_keys, filename):
    raw=SRC.read_text(encoding="utf-8-sig",errors="replace")
    lines=raw.splitlines()
    pairs=[]
    for i in range(0,len(lines)-1,2):
        try: code=int(lines[i].strip())
        except ValueError: continue
        pairs.append([code,lines[i+1]])

    # Locate LAYER table and add named layers if absent.
    existing_layers=set()
    for i,(c,v) in enumerate(pairs):
        if c==0 and v=="LAYER":
            for j in range(i+1,min(i+8,len(pairs))):
                if pairs[j][0]==2:
                    existing_layers.add(pairs[j][1]); break

    insert_layer_at=None; layer_count_idx=None; in_layer=False
    for i,(c,v) in enumerate(pairs):
        if c==0 and v=="TABLE" and i+1<len(pairs) and pairs[i+1]==[2,"LAYER"]:
            in_layer=True
            for j in range(i+2,min(i+8,len(pairs))):
                if pairs[j][0]==70: layer_count_idx=j; break
            continue
        if in_layer and c==0 and v=="ENDTAB":
            insert_layer_at=i; break
    new_layers=[x for x in LAYERS if x not in existing_layers]
    if insert_layer_at is not None and new_layers:
        rec=[]
        for nm in new_layers:
            rec.extend([[0,"LAYER"],[100,"AcDbSymbolTableRecord"],[100,"AcDbLayerTableRecord"],[2,nm],[70,"0"],[62,str(LAYERS[nm])],[6,"CONTINUOUS"]])
        pairs[insert_layer_at:insert_layer_at]=rec
        if layer_count_idx is not None:
            try: pairs[layer_count_idx][1]=str(int(pairs[layer_count_idx][1])+len(new_layers))
            except Exception: pass

    # Locate ENTITIES ENDSEC and inject world-coordinate design objects.
    in_entities=False; entity_end=None
    for i,(c,v) in enumerate(pairs):
        if c==0 and v=="SECTION" and i+1<len(pairs) and pairs[i+1]==[2,"ENTITIES"]:
            in_entities=True; continue
        if in_entities and c==0 and v=="ENDSEC": entity_end=i; break
    if entity_end is None: raise RuntimeError("ENTITIES end not found")

    inject=[]
    for key in include_keys:
        cn,_,layer_name,color=VARIANTS[key]
        inject += entity_pairs_from_string(lwpoly(world(variants[key]),layer_name,color))
    inject += entity_pairs_from_string(line(X0,Y0+WSE*SY,X0+current[-1][0]*SX,Y0+WSE*SY,"WSE_22_190",4))
    for pier,sta,elev in controls:
        x=X0+sta*SX; y=Y0+elev*SY
        inject += entity_pairs_from_string(circle(x,y,18,"PIER_CONTROL",6))
        inject += entity_pairs_from_string(text(x+25,y+10,22,f"{pier}# DESIGN Z={elev:.2f}m","ANNOTATION",6))
    pairs[entity_end:entity_end]=inject

    overlay=OUT/filename
    with overlay.open("w",encoding="utf-8",newline="\n") as f:
        for c,v in pairs: f.write(f"{c:>3}\n{v}\n")
    return overlay

build_overlay(["center","local","distributed"],"西支5断面_桥下设计河床_三方案叠加_R2013.dxf")
for key,(cn,_,_,_) in VARIANTS.items():
    build_overlay([key],f"西支5断面_桥下设计河床_{cn}_叠加_R2013.dxf")

print("DXF outputs:")
for p in sorted(OUT.glob("*.dxf")): print(" ",p.name,p.stat().st_size)
