#!/usr/bin/env python3
from pathlib import Path
from collections import Counter, defaultdict
import json, math, re, sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else 'data/dxf')
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else 'doc/dxf_inspection.json')


def read_text(path: Path):
    data = path.read_bytes()
    for enc in ('utf-8-sig', 'gb18030', 'cp936', 'latin1'):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return data.decode('latin1', errors='replace'), 'latin1-replace'


def pairs_from_text(text):
    lines = text.splitlines()
    pairs = []
    for i in range(0, len(lines)-1, 2):
        try:
            code = int(lines[i].strip())
        except ValueError:
            continue
        pairs.append((code, lines[i+1].rstrip('\r\n')))
    return pairs


def sanitize_text(s):
    s = s.replace('\\P', ' ').replace('\\~', ' ')
    s = re.sub(r'\\[A-Za-z][^;]*;', '', s)
    s = re.sub(r'\{\\[^}]*\}', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def inspect(path: Path):
    text, enc = read_text(path)
    pairs = pairs_from_text(text)
    version = None
    codepage = None
    entity_counts = Counter()
    layer_counts = Counter()
    text_items = []
    coord_x, coord_y, coord_z = [], [], []
    blocks = Counter()
    section = None
    in_entities = False
    entity = None
    entity_fields = []

    def flush_entity():
        nonlocal entity, entity_fields
        if not entity or not in_entities:
            entity = None; entity_fields = []; return
        entity_counts[entity] += 1
        layer = next((v for c,v in entity_fields if c == 8), None)
        if layer:
            layer_counts[layer] += 1
        if entity == 'INSERT':
            name = next((v for c,v in entity_fields if c == 2), None)
            if name: blocks[name] += 1
        if entity in ('TEXT','MTEXT','ATTRIB','ATTDEF'):
            chunks = [v for c,v in entity_fields if c in (1,3)]
            if chunks:
                t = sanitize_text(''.join(chunks))
                if t and len(text_items) < 400:
                    x = next((v for c,v in entity_fields if c == 10), None)
                    y = next((v for c,v in entity_fields if c == 20), None)
                    text_items.append({'type':entity,'layer':layer,'text':t,'x':x,'y':y})
        # approximate extents from common coordinate group codes
        vals = defaultdict(list)
        for c,v in entity_fields:
            if 10 <= c <= 18 or 20 <= c <= 28 or 30 <= c <= 38:
                try: vals[c].append(float(v))
                except ValueError: pass
        for c, vs in vals.items():
            if 10 <= c <= 18: coord_x.extend(vs)
            elif 20 <= c <= 28: coord_y.extend(vs)
            elif 30 <= c <= 38: coord_z.extend(vs)
        entity = None; entity_fields = []

    i = 0
    while i < len(pairs):
        c,v = pairs[i]
        if c == 9 and v == '$ACADVER' and i+1 < len(pairs):
            version = pairs[i+1][1]
        if c == 9 and v == '$DWGCODEPAGE' and i+1 < len(pairs):
            codepage = pairs[i+1][1]
        if c == 0 and v == 'SECTION':
            flush_entity()
            if i+1 < len(pairs) and pairs[i+1][0] == 2:
                section = pairs[i+1][1]
                in_entities = section == 'ENTITIES'
            i += 2; continue
        if c == 0 and v == 'ENDSEC':
            flush_entity(); section = None; in_entities = False
        elif in_entities and c == 0:
            flush_entity(); entity = v; entity_fields = []
        elif in_entities and entity:
            entity_fields.append((c,v))
        i += 1
    flush_entity()

    extents = None
    if coord_x and coord_y:
        extents = {
            'xmin': min(coord_x), 'xmax': max(coord_x),
            'ymin': min(coord_y), 'ymax': max(coord_y),
            'width': max(coord_x)-min(coord_x), 'height': max(coord_y)-min(coord_y),
        }
        if coord_z:
            extents.update({'zmin':min(coord_z),'zmax':max(coord_z)})

    keywords = ['断面','高程','河床','桥','墩','冲刷','水位','设计','现状','赣江','西支','里程','桩号','米','m']
    hits = []
    for item in text_items:
        if any(k.lower() in item['text'].lower() for k in keywords):
            hits.append(item)

    return {
        'file': str(path), 'bytes': path.stat().st_size, 'encoding': enc,
        'acadver': version, 'codepage': codepage,
        'entity_counts': entity_counts.most_common(),
        'layer_counts': layer_counts.most_common(40),
        'insert_blocks': blocks.most_common(30),
        'approx_extents': extents,
        'text_count_captured': len(text_items),
        'keyword_texts': hits[:160],
        'text_samples': text_items[:100],
    }

files = sorted([p for p in ROOT.glob('*.dxf') if p.is_file()])
results = [inspect(p) for p in files]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Wrote {OUT} for {len(results)} DXF files')
for r in results:
    print('\n'+Path(r['file']).name)
    print('  size:', r['bytes'], 'acad:', r['acadver'], 'encoding:', r['encoding'])
    print('  entities:', r['entity_counts'][:12])
    print('  layers:', r['layer_counts'][:10])
    print('  extents:', r['approx_extents'])
    print('  keyword texts:')
    for x in r['keyword_texts'][:20]:
        print('   -', x['text'][:140])
