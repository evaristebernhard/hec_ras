#!/usr/bin/env python3
from pathlib import Path
from collections import Counter, defaultdict
import math, re

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'data' / 'intermediate' / 'dxf' / '西支5断面100-100，0906.dxf'
raw = path.read_text(encoding='utf-8-sig', errors='replace').splitlines()
pairs=[]
for i in range(0,len(raw)-1,2):
    try: pairs.append((int(raw[i].strip()), raw[i+1].rstrip()))
    except: pass

entities=[]
in_ent=False; cur=None; fields=[]
def flush():
    global cur, fields
    if cur and in_ent:
        entities.append((cur,fields))
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
    for cc,v in f:
        if cc==c:return v
    return default

def nums(f,c):
    out=[]
    for cc,v in f:
        if cc==c:
            try:out.append(float(v))
            except:pass
    return out

print('Entity total',len(entities))
# Per layer type counts
st=defaultdict(Counter)
for typ,f in entities:
    st[one(f,8,'0')][typ]+=1
for layer,c in sorted(st.items(), key=lambda kv:-sum(kv[1].values())):
    print('LAYER',layer,sum(c.values()),dict(c))

# Texts with positions
texts=[]
for typ,f in entities:
    if typ=='TEXT':
        t=one(f,1,'').strip(); x=one(f,10); y=one(f,20); layer=one(f,8,'0')
        try:x=float(x);y=float(y)
        except:continue
        texts.append((y,x,layer,t))
print('\nTEXT SAMPLE sorted top-to-bottom (first 220):')
for y,x,layer,t in sorted(texts, reverse=True)[:220]:
    print(f'{x:12.3f} {y:12.3f} [{layer}] {t}')

# Identify named section labels and nearest texts within 250 drawing units
labels=[r for r in texts if '西支' in r[3]]
for ly,lx,ll,lt in labels:
    print('\n===',lt,'at',lx,ly,'===')
    near=[]
    for y,x,layer,t in texts:
        d=math.hypot(x-lx,y-ly)
        if d<300:
            near.append((d,x,y,layer,t))
    for d,x,y,layer,t in sorted(near)[:80]:
        print(f'd={d:8.2f} x={x:12.3f} y={y:12.3f} [{layer}] {t}')

# LWPOLYLINE summary: vertices are repeated 10/20 pairs in entity fields
polys=[]
for typ,f in entities:
    if typ!='LWPOLYLINE':continue
    layer=one(f,8,'0'); xs=nums(f,10); ys=nums(f,20); n=min(len(xs),len(ys))
    if not n:continue
    xs=xs[:n];ys=ys[:n]
    length=sum(math.hypot(xs[j]-xs[j-1],ys[j]-ys[j-1]) for j in range(1,n))
    polys.append((length,n,layer,min(xs),max(xs),min(ys),max(ys),xs,ys))
print('\nTOP 60 LWPOLYLINE BY LENGTH:')
for p in sorted(polys, reverse=True)[:60]:
    length,n,layer,x0,x1,y0,y1,_,_=p
    print(f'len={length:12.3f} n={n:4d} [{layer}] bbox=({x0:.3f},{y0:.3f})-({x1:.3f},{y1:.3f})')

# Lines with large span
lines=[]
for typ,f in entities:
    if typ!='LINE':continue
    try:
        x1=float(one(f,10)); y1=float(one(f,20)); x2=float(one(f,11)); y2=float(one(f,21));
    except:continue
    L=math.hypot(x2-x1,y2-y1); layer=one(f,8,'0')
    lines.append((L,layer,x1,y1,x2,y2))
print('\nTOP 60 LINE BY LENGTH:')
for q in sorted(lines, reverse=True)[:60]:
    L,layer,x1,y1,x2,y2=q
    print(f'len={L:12.3f} [{layer}] ({x1:.3f},{y1:.3f})->({x2:.3f},{y2:.3f})')
