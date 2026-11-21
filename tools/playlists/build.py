from common import complete
import csv, json, math, random, re, collections
exec(open('match.py').read().split("json.dump({'alb'")[0])   # norm, find, alb, meta
m = json.load(open('matches.json'))
canon_names = ["1001 Albums You Must Hear Before You Die", "Rolling Stone's 500 Greatest Albums of All Time",
  "NME's 500 Greatest Albums of All Time", '/mu/ Essentials', 'Fantano Top 200 Albums of 2010s', 'Mercury Prize',
  'Pitchfork Album of the Year', 'Grammy for Album of the Year', 'Brit Award for British Album of the Year']
canon = collections.Counter()
for r in csv.reader(open('spreadsheet.csv')):
    lists = [t.strip() for t in r[5].split(';')]
    n = sum(1 for t in lists if t in canon_names)
    if n:
        f = find(r[2], r[1])
        if f: canon[f] = max(canon[f], n)
accrank = {}
for a, b, y, f in m['Acclaimed Music Top 3000']:
    if f and f not in accrank: accrank[f] = None
for i, x in enumerate(json.load(open('acclaimed.json'))):
    pass
for a, b, y, f in m['Acclaimed Music Top 3000']: pass
acc = json.load(open('acclaimed.json'))
for x, (a, b, y, f) in zip(acc, m['Acclaimed Music Top 3000']):
    if f and (accrank.get(f) is None): accrank[f] = x['rank']
plays = {}
for r in csv.DictReader(open('plan.csv'), delimiter=';'):
    f = find(r['interpret'], r['album'])
    if f and r['lastfm_plays'].isdigit(): plays[f] = max(plays.get(f, 0), int(r['lastfm_plays']))
taste = {norm(s['name']): s['score'] for s in json.load(open('seeds.json'))}
BAD = re.compile(r'\b(live|best of|greatest hits|collection|anthology|essential|bootleg|hits|sessions|unplugged|mtv)\b', re.I)
NOART = {norm('Die drei ???'), norm('TKKG'), norm('Benjamin Blümchen')}
rows = []
for f in set(canon) | set(accrank) | set(plays):
    artist, album = meta[f]
    if not complete(alb[f]) or len(alb[f]) < 6 or BAD.search(album) or norm(artist) in NOART: continue
    crit = (3 * (1 - accrank[f] / 3000) if accrank.get(f) else 0) + 0.75 * canon.get(f, 0)
    p = plays.get(f, 0); pop = min(1.5, max(0, (math.log10(p) - 5) / 2)) if p else 0
    t = taste.get(norm(artist), 0); tb = 0.75 * min(1, math.log10(1 + t) / math.log10(50))
    rows.append((crit + pop + tb, crit, pop, tb, f))
rows.sort(reverse=True)
per = collections.Counter(); top = []
for r in rows:
    a = norm(meta[r[4]][0])
    if per[a] >= 2: continue
    per[a] += 1; top.append(r)
    if len(top) == 250: break
json.dump({'top': top, 'accrank': accrank}, open('top250.json', 'w'))
for i, (s, c, p, tb, f) in enumerate(top, 1):
    print(f"{i:3} {s:4.2f} (K{c:.1f} L{p:.1f} G{tb:.1f}) {meta[f][0]} – {meta[f][1]}")
