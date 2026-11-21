import json, random, csv, os, sys, re
exec(open('match.py').read().split("json.dump({'alb'")[0])
m = json.load(open('matches.json')); top = json.load(open('top250.json'))['top']
from common import complete, clean_tracks
def tracks(f): return clean_tracks(alb[f])
def year(f):
    y = re.match(r'(\d{4})', f.split('\\')[3]); return int(y.group(1)) if y else 0
def uniq(seq):
    s=set(); return [x for x in seq if x and complete(alb[x]) and not (x in s or s.add(x))]
def rel(p, style):
    p = p.rstrip('\x00')
    if style == 'rel': return '../' + p[3:].replace('\\', '/')       # a:\Music\.. -> ../Music/..
    if style == 'abs': return p                                       # a:\Music\..
    if style == 'win': return p[2:]                                   # \Music\..
def write(name, folders, style="abs", outdir='out'):
    os.makedirs(outdir, exist_ok=True)
    n = 0
    with open(f'{outdir}/{name}.m3u', 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write('#EXTM3U\n')
        for f in folders:
            for t in tracks(f): fh.write(rel(t, style) + '\n'); n += 1
    return n
PLAYLISTS = {}
acc = uniq([h[3] for h in m['Acclaimed Music Top 3000']])
PLAYLISTS['Acclaimed Top 3000'] = acc
for key, short in [("1001 Albums You Must Hear Before You Die", '1001 Albums'),
                   ("Rolling Stone's 500 Greatest Albums of All Time", 'Rolling Stone 500'),
                   ("NME's 500 Greatest Albums of All Time", 'NME 500'), ('/mu/ Essentials', 'mu Essentials'),
                   ('Fantano Top 200 Albums of 2010s', 'Fantano 2010er'), ('Mercury Prize', 'Mercury Prize'),
                   ('Pitchfork Album of the Year', 'Pitchfork Album des Jahres')]:
    PLAYLISTS[short] = sorted(uniq([h[3] for h in m[key]]), key=year)
t = [r[4] for r in top]; random.Random(250).shuffle(t); PLAYLISTS['Top 250 Alben'] = t
if __name__ == '__main__':
    for k, v in PLAYLISTS.items(): print(len(v), sum(len(alb[f]) for f in v), k)
