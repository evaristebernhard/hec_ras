#!/usr/bin/env python3
from pathlib import Path
import csv

ROOT=Path('data/processed/cross_sections')
LEVELS=[14.960,22.190]

def read_profile(path):
    rows=[]
    with path.open(encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            rows.append((float(r['station_m_raw_direction']),float(r['elevation_m'])))
    rows.sort()
    return rows

def seg_area(x1,z1,x2,z2,w):
    # integrate max(w-z(x),0) over a linear segment
    b1=w-z1; b2=w-z2
    dx=x2-x1
    if dx<=0:return 0.0,0.0
    if b1<=0 and b2<=0:return 0.0,0.0
    if b1>=0 and b2>=0:return dx*(b1+b2)/2.0,dx
    # one endpoint submerged: locate crossing
    t=b1/(b1-b2)
    xc=x1+t*dx
    if b1>0:
        wet=xc-x1
        return wet*b1/2.0,wet
    wet=x2-xc
    return wet*b2/2.0,wet

def metrics(p,w):
    area=width=0.0
    for (x1,z1),(x2,z2) in zip(p,p[1:]):
        a,wd=seg_area(x1,z1,x2,z2,w); area+=a;width+=wd
    return area,width,(area/width if width else 0)

for path in sorted(ROOT.glob('*.csv')):
    if path.name=='summary.csv':continue
    p=read_profile(path)
    print(path.stem)
    for w in LEVELS:
        a,tw,md=metrics(p,w)
        print(f'  WSE={w:.3f} m: area={a:.1f} m2, wetted horizontal width={tw:.1f} m, mean depth={md:.2f} m')
