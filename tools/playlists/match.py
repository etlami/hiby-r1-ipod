import csv, json, re, sqlite3, unicodedata, collections, sys
def norm(s):
    s = (s or '').split(' = ')[0].replace('_',' ')
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower()
    s = s.replace('&',' and ')
    s = re.sub(r'\(.*?\)|\[.*?\]', ' ', s)
    s = re.sub(r'\b(the|a|an|deluxe|edition|remaster(ed)?|expanded|version|anniversary)\b', ' ', s)
    return re.sub(r'[^a-z0-9]+', '', s)
db = sqlite3.connect(__import__('os').environ.get('HIBY_DB', 'usrlocal_media.db'))
alb = collections.defaultdict(list)   # folder -> rows
for p, art, aa, al in db.execute("select path,artist,album_artist,album from MEDIA_TABLE"):
    p = p.rstrip('\x00'); folder = p.rsplit('\\',1)[0]
    alb[folder].append(p)
meta = {}
for folder in alb:
    parts = folder.split('\\')   # a:, Music, Interpret, Jahr - Album
    if len(parts) < 4: continue
    artist = parts[2]; album = re.sub(r'^\d{4} - ', '', parts[3])
    meta[folder] = (artist, album)
idx = collections.defaultdict(list)
for f,(ar,al) in meta.items(): idx[(norm(ar), norm(al))].append(f)
byalbum = collections.defaultdict(list)
for f,(ar,al) in meta.items(): byalbum[norm(al)].append((norm(ar), f))
byartist = collections.defaultdict(list)
for f,(ar,al) in meta.items(): byartist[norm(ar)].append(f)
import html
def find(artist, album):
    album = html.unescape(album); artist = html.unescape(artist)
    alts = [album] + [x for x in re.split(r'\s*/\s*', album) if x != album]
    for alt in alts:
        if (norm(artist), norm(alt)) in idx: return idx[(norm(artist), norm(alt))][0]
    k = (norm(artist), norm(album))
    # Interpret enthalten (z. B. "Bob Dylan" vs "Bob Dylan and The Band")
    for na, f in byalbum.get(k[1], []):
        if na and k[0] and (na in k[0] or k[0] in na): return f
    # gleicher Interpret, Album enthält das andere (>= 8 Zeichen) oder Wortmenge fast gleich
    wa = set(words(album))
    for f in byartist.get(k[0], []):
        ca = norm(meta[f][1])
        short, long_ = sorted([ca, k[1]], key=len)
        extra = long_.replace(short, '', 1)
        if (len(short) >= 8 and short in long_ and short != k[0]
                and not re.fullmatch(r'(vol)?[0-9ivx]+', extra)
                and ('live' in ca) == ('live' in k[1])):
            return f
        wb = set(words(meta[f][1]))
        if wa and wb and ('live' in wa) == ('live' in wb) and len(wa & wb) / len(wa | wb) >= 0.75: return f
    return None
def words(s):
    s = unicodedata.normalize('NFKD', (s or '').replace('_',' ')).encode('ascii','ignore').decode().lower()
    return [w for w in re.findall(r'[a-z0-9]+', s) if w not in ('the','a','an','of','and')]
json.dump({'alb': alb, 'meta': meta}, open('card_albums.json','w'))
lists = collections.defaultdict(list)
for r in csv.reader(open('spreadsheet.csv')):
    for t in r[5].split(';'):
        lists[t.strip()].append((r[2], r[1], r[3]))
acc = json.load(open('acclaimed.json'))
lists['Acclaimed Music Top 3000'] = [(a['artist'], a['album'], a['year']) for a in acc]
out = {}
for name in ['Acclaimed Music Top 3000', "1001 Albums You Must Hear Before You Die", "Rolling Stone's 500 Greatest Albums of All Time", "NME's 500 Greatest Albums of All Time", 'Fantano Top 200 Albums of 2010s', 'Mercury Prize', 'Pitchfork Album of the Year', '/mu/ Essentials']:
    L = lists[name]; hit = [(a,b,y,find(a,b)) for a,b,y in L]
    out[name] = hit
    print(f"{sum(1 for h in hit if h[3])}/{len(L)}  {name}")
json.dump(out, open('matches.json','w'), indent=0)
