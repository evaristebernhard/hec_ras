#!/usr/bin/env python3
from pathlib import Path
from collections import defaultdict
from statistics import median
import csv, math, re

SRC = Path('data/dxf/西支5断面100-100，0906.dxf')
OUT = Path('data/processed/cross_sections')
OUT.mkdir(parents=True, exist_ok=True)

lines = SRC.read_text(encoding='utf-8-sig', errors='replace').splitlines()
pairs=[]
for i in range(0,len(lines)-1,2):
    try: pairs.append((int(lines[i].strip()), lines[i+1].rstrip()))
    except ValueError: pass

entities=[]; in_ent=False; cur=None; fields=[]
def flush():
    global cur,fields
    if cur and in_ent: entities.append((cur,fields))
    cur=None; fields=[]
i=0
while i<len(pairs):
    c,v=pairs[i]
    if c==0 and v=='SECTION' and i+1<len(pairs) and pairs[i+1]==(2,'ENTITIES'):
        in_ent=True; i+=2; continue
    if c==0 and v=='ENDSEC' and in_ent:
        flush(); in_ent=False
    elif in_ent and c==0:
        flush(); cur=v; fields=[]
    elif in_ent and cur:
        fields.append((c,v))
    i+=1
flush()

def one(f,c,default=None):
    return next((v for cc,v in f if cc==c),default)
def nums(f,c):
    out=[]
    for cc,v in f:
        if cc==c:
            try: out.append(float(v))
            except: pass
    return out

texts=[]
for typ,f in entities:
    if typ=='TEXT':
        try:x=float(one(f,10)); y=float(one(f,20))
        except:continue
        texts.append({'layer':one(f,8,'0'),'text':one(f,1,'').strip(),'x':x,'y':y})

labels=[t for t in texts if t['layer']=='DLSS']
profiles=[]
for typ,f in entities:
    if typ!='LWPOLYLINE' or one(f,8,'0')!='DMX': continue
    xs=nums(f,10); ys=nums(f,20); n=min(len(xs),len(ys)); xs=xs[:n]; ys=ys[:n]
    if n<2: continue
    profiles.append({'xs':xs,'ys':ys,'xmin':min(xs),'xmax':max(xs),'ymin':min(ys),'ymax':max(ys)})

profiles.sort(key=lambda p:p['ymax'], reverse=True)
summary=[]
for p in profiles:
    # section name = closest DLSS label in vertical direction
    lab=min(labels, key=lambda t:abs(t['y']-p['ymax']))
    name=lab['text']
    # axis tick labels are on zdm1, numeric, near left/right profile edges, and around profile elevation range
    ticks=[]
    for t in texts:
        if t['layer']!='zdm1': continue
        try: val=float(t['text'])
        except: continue
        if not (-20 <= val <= 60): continue
        near_edge=min(abs(t['x']-p['xmin']),abs(t['x']-p['xmax'])) < 100
        if not near_edge: continue
        if p['ymin']-120 <= t['y'] <= p['ymax']+120:
            ticks.append((val,t['y']))
    # robustly infer y = y0 + scale*elevation. Estimate from all pair slopes then median.
    slopes=[]
    uniq=[]
    for val,y in ticks:
        if all(abs(val-v)>1e-9 or abs(y-yy)>1e-6 for v,yy in uniq): uniq.append((val,y))
    for a in range(len(uniq)):
        for b in range(a+1,len(uniq)):
            dv=uniq[b][0]-uniq[a][0]
            if abs(dv)>=5:
                slopes.append((uniq[b][1]-uniq[a][1])/dv)
    scale=median(slopes) if slopes else 10.0
    # avoid mixing any accidental ticks from nearby sections
    if not (8.0 <= abs(scale) <= 12.0): scale=10.0
    intercepts=[y-scale*val for val,y in ticks]
    y0=median(intercepts) if intercepts else None
    if y0 is None:
        raise RuntimeError(f'Cannot calibrate elevation axis for {name}')

    # Horizontal scale confirmed by drawing note and distance annotations: 10 CAD units = 1 m.
    x0=p['xs'][0]  # preserve drawing direction; HEC-RAS orientation will be checked against plan view later.
    rows=[]
    for idx,(x,y) in enumerate(zip(p['xs'],p['ys'])):
        station=(x-x0)/10.0
        elev=(y-y0)/scale
        rows.append((idx,station,elev,x,y))

    safe=re.sub(r'[\\/:*?"<>| ]+','_',name)
    out=OUT/f'{safe}.csv'
    with out.open('w',encoding='utf-8-sig',newline='') as fh:
        w=csv.writer(fh); w.writerow(['point_index','station_m_raw_direction','elevation_m','cad_x','cad_y']); w.writerows(rows)
    st=[r[1] for r in rows]; el=[r[2] for r in rows]
    summary.append((name,len(rows),st[0],st[-1],min(st),max(st),min(el),max(el),scale,y0,out))

with (OUT/'summary.csv').open('w',encoding='utf-8-sig',newline='') as fh:
    w=csv.writer(fh)
    w.writerow(['section','points','station_first_m','station_last_m','station_min_m','station_max_m','elev_min_m','elev_max_m','vertical_scale_cad_per_m','elev0_cad_y','csv'])
    for s in summary:
        w.writerow([*s[:-1],str(s[-1])])

print('Extracted',len(summary),'cross sections from DMX polylines')
for s in summary:
    name,n,st0,st1,smin,smax,emin,emax,scale,y0,out=s
    print(f'{name}: {n} pts, station {smin:.1f}..{smax:.1f} m (drawn first={st0:.1f}, last={st1:.1f}), elev {emin:.2f}..{emax:.2f} m, scale={scale:.3f}, y0={y0:.3f}')
    print(' ->',out)
