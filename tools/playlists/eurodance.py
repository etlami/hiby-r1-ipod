"""Eurodance-Playlists aus der HiBy-DB.
  Eurodance - Hits : Last.fm-Top-10 je Interpret (ed_top.json), Originalversion
  Eurodance - Alles: jedes Lied einmal (Original > Radio-Edit > Remix), keine Instrumentals
Aufruf: python3 eurodance.py <usrlocal_media.db> [outdir]"""
import sqlite3, sys, re, json, random, unicodedata, os, collections

ARTISTS = ["Haddaway", "La Bouche", "Culture Beat", "Real McCoy", "U96", "E-Rotic", "Captain Jack", "Masterboy",
           "Captain Hollywood Project", "Maxx", "Corona", "2 Unlimited", "Dr. Alban", "Technotronic", "Whigfield",
           "Ice MC", "Cappella", "N-Trance", "Eiffel 65", "Gigi D'Agostino", "Vengaboys", "Scatman John", "Rednex",
           "DJ BoBo", "Sash!", "Aqua", "Mr. President", "Snap!"]
ALIAS = {"capella": "cappella"}
VER = r"(mix|remix|rmx|edit|version|extended|club|dub|radio|single|airplay|vocal|original|12\"|7\"|12 inch|7 inch|cut|re-?work|bootleg|instrumental|a ?cappella|live|demo|reprise|remaster(ed)?|mono|stereo)"
RADIO = re.compile(r"radio|single|airplay|short|7\"|7 inch", re.I)
DROP = re.compile(r"instrumental|a ?cappella|karaoke|^intro$|^outro$|^interlude$|megamix|medley", re.I)

def an(s):
    s = unicodedata.normalize("NFKD", s.replace("‐", "-").replace("’", "'")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]", "", s)
    return ALIAS.get(s, s)

def split(title):
    """-> (Grundtitel-Schlüssel, Versionsrang 0/1/2, verwerfen?)"""
    t = title.replace("’", "'").strip()
    tags = []
    def grab(m):
        inner = m.group(1)
        if re.search(VER, inner, re.I): tags.append(inner); return ""
        return " " + inner + " "            # inhaltliche Klammer (z. B. "Life (Everybody Needs …)") bleibt
    t = re.sub(r"[\(\[]([^\)\]]*)[\)\]]", grab, t)
    m = re.search(r"\s[-–]\s(.*)$", t)    # "Titel - Extended Mix"
    if m and re.search(VER, m.group(1), re.I): tags.append(m.group(1)); t = t[:m.start()]
    m = re.search(r"\s+(remix|rmx|rap)\s*$", t, re.I)   # "Captain Jack Remix (…)"
    if m: tags.append(m.group(1)); t = t[:m.start()]
    if tags:
        m = re.search(r"\s+(19|20)\d\d\s*$", t)          # "Das Boot 2001 (radio edit)"
        if m: tags.append("year"); t = t[:m.start()]
    base = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"\bfeat\.?.*$|\bft\..*$", "", base)
    base = re.sub(r"[^a-z0-9]", "", base)
    tg = " ".join(tags)
    drop = bool(DROP.search(tg)) or bool(DROP.search(title.strip())) or not base
    if not tags or re.fullmatch(r"\s*(album|original)( version| mix)?\s*|\s*remaster(ed)?.*", tg, re.I): rank = 0
    elif RADIO.search(tg) and not re.search(r"remix|rmx", tg, re.I): rank = 1
    else: rank = 2
    plain = re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", re.sub(r"[\(\[].*?[\)\]]", "", title.replace("’", "'"))).encode("ascii", "ignore").decode().lower())
    return base, rank, drop, plain

def main(db, outdir="out"):
    want = {an(a): a for a in ARTISTS}
    con = sqlite3.connect(db)
    songs = collections.defaultdict(list)          # (artist, base) -> [(rank, year, path)]
    for path, name in con.execute("select path, name from MEDIA_TABLE"):
        p = path.rstrip("\x00"); parts = p.split("\\")
        if len(parts) < 5: continue
        a = an(parts[2])
        if a not in want: continue
        base, rank, drop, plain = split(name.rstrip("\x00"))
        if drop: continue
        y = re.match(r"(\d{4})", parts[3]); y = int(y.group(1)) if y else 9999
        songs[(a, base)].append((rank, y, p, plain))
    # inhaltliche Klammer, deren Titel es auch ohne Klammer gibt -> nur Version ("Mr. Vain (Mr. Trance)")
    for k in list(songs):
        if k not in songs: continue
        plain = songs[k][0][3]
        if plain != k[1] and (k[0], plain) in songs:
            songs[(k[0], plain)] += [(2, y, p, pl) for _, y, p, pl in songs.pop(k)]
    best = {k: sorted(v)[0] for k, v in songs.items()}
    alles = [v[2] for v in best.values()]

    top = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ed_top.json")))
    hits = []; per = {}
    for a, tracks in top.items():
        k = an(a); n = 0; seen = set()
        for title, _ in tracks:
            base, _, drop, _ = split(title)
            if drop or base in seen or (k, base) not in best: continue
            seen.add(base); hits.append(best[(k, base)][2]); n += 1
            if n == 10: break
        per[a] = n

    def mix(lst, seed):
        # mischen, aber nicht zweimal derselbe Interpret hintereinander (soweit möglich)
        r = random.Random(seed); lst = lst[:]; r.shuffle(lst); out = []
        while lst:
            i = next((j for j, x in enumerate(lst) if not out or x.split("\\")[2] != out[-1].split("\\")[2]), 0)
            out.append(lst.pop(i))
        return out
    os.makedirs(outdir, exist_ok=True)
    for name, lst, seed in [("Eurodance - Hits", hits, 90), ("Eurodance - Alles", alles, 91)]:
        with open(f"{outdir}/{name}.m3u", "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write("#EXTM3U\n")
            for p in mix(lst, seed): fh.write(p + "\n")
        print(len(lst), name)
    print("Hits je Interpret:", {a: n for a, n in per.items()})
    return best, songs

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "out")
