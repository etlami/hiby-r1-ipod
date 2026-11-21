#!/usr/bin/env python3
"""HiBy-R1-Musikdatenbank (usrlocal_media.db) ohne Gerätescan bauen.

Eingaben:
  --vorlage  echte, vom HiBy erzeugte DB (Schema + VERSION_TABLE)
  --ctime    `ls -lRc --full-time Music .Music_alle` von der Karte
  --mtime    `ls -lR  --full-time Music .Music_alle` von der Karte
  --src      Server-Kopie der Musik (Interpret/Jahr - Album/NN - Titel.ext)
Regeln (aus Vorlage abgeleitet):
  path   a:\\Music\\...  (Backslashes)
  ctime  Datei-ctime auf der Karte; mtime = mtime des Albumordners
  ids    fortlaufend in Pfadreihenfolge; Album/Interpret/Genre-id = erste Media-id
  pinyin  Kodierung je Zeichen + '##' + Großbuchstaben (nur ASCII); MEDIA mit NUL am Ende
"""
import argparse, os, re, sqlite3, sys, shutil, datetime, collections
from concurrent.futures import ProcessPoolExecutor

LETTER = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", [
    0x4e00, 0x4ebb, 0x522c, 0x5743, 0x5b1b, 0x5bcb, 0x5e3b, 0x617d, 0x658c, 0x658d,
    0x6bef, 0x6e23, 0x7440, 0x7763, 0x7932, 0x7955, 0x7baf, 0x7fa4, 0x80e4, 0x85f5,
    0x896a, 0x896b, 0x896c, 0x8bd9, 0x9101, 0x98cd]))
AUDIO = {"opus": 2373, "mp3": 85}
FMTNAME = {2373: "OPUS", 85: "MP3"}

def upper_ascii(s):
    return "".join(chr(ord(c) - 32) if "a" <= c <= "z" else c for c in s)

def pinyin(s, nul=False):
    up = upper_ascii(s)
    enc = []
    for c in up:
        o = ord(c)
        if c in LETTER: enc.append(chr(LETTER[c]))
        elif 0x3400 <= o <= 0x9fff: enc.append(c)          # CJK: Tabelle unbekannt, Zeichen selbst
        elif o + 0xA0A4 <= 0xFFFF: enc.append(chr(o + 0xA0A4))
        else: enc.append(c)
    return "".join(enc) + "##" + up + "\x00"

Z = lambda s: s + "\x00"   # HiBy speichert Texte inkl. C-Endzeichen

def first_char(s):
    up = upper_ascii(s)
    return up[:1]

LS_RE = re.compile(r"^(\S+)\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ([+-]\d{4}) (.*)$")
ANSI = re.compile(r"\x1b\[[0-9;]*m")

def to_epoch(d, tz):
    t = datetime.datetime.strptime(d + " " + tz, "%Y-%m-%d %H:%M:%S %z")
    return int(t.timestamp())

def parse_ls(fn):
    """-> dict relpath -> (isdir, size, epoch); relpath mit Music/ statt .Music_alle/"""
    out = {}; cur = None
    for raw in open(fn, encoding="utf-8", errors="surrogateescape"):
        line = ANSI.sub("", raw.rstrip("\r\n"))
        if not line: continue
        if line.endswith(":") and not LS_RE.match(line):
            cur = line[:-1]
            if cur.startswith(".Music_alle"): cur = "Music" + cur[len(".Music_alle"):]
            continue
        if line.startswith("total "): continue
        m = LS_RE.match(line)
        if not m or cur is None: continue
        perm, size, d, tz, name = m.groups()
        out[cur + "/" + name] = (perm.startswith("d"), int(size), to_epoch(d, tz))
    return out

def _fast_last_granule(fileobj, serial):
    """Letzte Ogg-Seite vom Dateiende her suchen (statt ganze Datei zu lesen)."""
    import struct
    fileobj.seek(0, 2); end = fileobj.tell()
    for back in (65536, 1 << 20):
        start = max(0, end - back); fileobj.seek(start); buf = fileobj.read(end - start)
        i = buf.rfind(b"OggS")
        while i >= 0:
            if len(buf) >= i + 27:
                gran, ser = struct.unpack("<qI", buf[i + 6:i + 18])
                if ser == serial and gran >= 0:
                    return gran
            i = buf.rfind(b"OggS", 0, i)
        if start == 0: break
    return None

def _patch_mutagen():
    from mutagen import oggopus
    def _post_tags(self, fileobj):
        g = _fast_last_granule(fileobj, self.serial)
        pre = self._OggOpusInfo__pre_skip
        self.length = ((g - pre) / 48000.0) if g is not None else 0.0
    oggopus.OggOpusInfo._post_tags = _post_tags

def read_tags(args):
    rel, src = args
    import mutagen
    _patch_mutagen()
    p = os.path.join(src, rel.split("/", 1)[1])
    if not os.path.exists(p):   # Server-Namen teils NFD, Karte NFC
        import unicodedata
        for f in ("NFD", "NFC"):
            q = unicodedata.normalize(f, p)
            if os.path.exists(q): p = q; break
        else:   # gemischt: Verzeichnis für Verzeichnis abgleichen
            d = src
            for part in rel.split("/")[1:]:
                n = unicodedata.normalize("NFC", part)
                hit = [x for x in os.listdir(d) if unicodedata.normalize("NFC", x) == n] if os.path.isdir(d) else []
                d = os.path.join(d, hit[0] if hit else part)
            p = d
    if not os.path.exists(p) and "?" in p:
        import fnmatch
        d, n = os.path.split(p)
        try:
            hits = [x for x in os.listdir(d) if fnmatch.fnmatchcase(x, n.replace("[", "[[]"))]
        except OSError:
            hits = []
        if len(hits) == 1: p = os.path.join(d, hits[0])
    r = {"ok": False}
    try:
        f = mutagen.File(p)
    except Exception as e:
        return rel, {"ok": False, "err": str(e)}
    if f is None: return rel, {"ok": False, "err": "unbekannt"}
    ext = rel.rsplit(".", 1)[1].lower()
    def tag(*keys):
        for k in keys:
            v = f.tags.get(k) if f.tags is not None else None
            if v is None: continue
            if hasattr(v, "text"): v = v.text
            if isinstance(v, (list, tuple)):
                v = [str(x) for x in v if str(x)]
                if v: return v
            elif str(v): return [str(v)]
        return None
    if ext == "opus":
        t = lambda k: tag(k)
        info = f.info
        pre = getattr(info, "_OggOpusInfo__pre_skip", 0)
        raw_len = info.length + pre / 48000.0
        r.update(sr=48000, ch=info.channels, raw_len=raw_len, br=None)
        title, album, artist, aa, genre = t("title"), t("album"), t("artist"), t("albumartist"), t("genre")
        date, trk, disc = t("date") or t("year"), t("tracknumber"), t("discnumber")
    else:
        info = f.info
        r.update(sr=info.sample_rate, ch=info.channels, raw_len=info.length, br=info.bitrate)
        title, album, artist, aa, genre = tag("TIT2"), tag("TALB"), tag("TPE1"), tag("TPE2"), tag("TCON")
        date, trk, disc = tag("TDRC", "TYER"), tag("TRCK"), tag("TPOS")
    def num(v, d):
        try: return int(str(v[0]).split("/")[0].strip())
        except Exception: return d
    y = 0
    if date:
        mm = re.match(r"\s*(\d{4})", str(date[0]))
        if mm: y = int(mm.group(1))
    r.update(ok=True, title=title[0] if title else None, album=album[0] if album else None,
             artist=artist[0] if artist else None, aa=aa[0] if aa else "",
             genre=";".join(genre) if genre else "", year=y, trk=num(trk, 0), disc=num(disc, 1))
    return rel, r

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vorlage", required=True); ap.add_argument("--ctime", required=True)
    ap.add_argument("--mtime", required=True); ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--only", help="nur Pfade mit diesem Präfix (Test)", action="append")
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()

    ct = parse_ls(a.ctime); mt = parse_ls(a.mtime)
    files = sorted(k for k, v in mt.items() if not v[0] and k.rsplit(".", 1)[-1].lower() in AUDIO)
    if a.only: files = [k for k in files if any(k.startswith(o) for o in a.only)]
    print("Dateien auf der Karte:", len(files), file=sys.stderr)

    import pickle
    cache = a.out + ".tags.pkl"
    tags = pickle.load(open(cache, "rb")) if os.path.exists(cache) else {}
    todo = [k for k in files if k not in tags or not tags[k]["ok"]]
    print("aus Cache:", len(files) - len(todo), "neu zu lesen:", len(todo), file=sys.stderr)
    with ProcessPoolExecutor(a.jobs) as ex:
        for i, (k, v) in enumerate(ex.map(read_tags, [(k, a.src) for k in todo], chunksize=200)):
            tags[k] = v
            if i % 5000 == 4999:
                pickle.dump(tags, open(cache, "wb")); print("  gelesen", i + 1, file=sys.stderr, flush=True)
    pickle.dump(tags, open(cache, "wb"))
    fehl = [k for k in files if not tags[k]["ok"]]
    print("ohne Tags/nicht auf Server:", len(fehl), file=sys.stderr)
    for k in fehl[:20]: print("  ", k, tags[k].get("err"), file=sys.stderr)

    shutil.copy(a.vorlage, a.out)
    db = sqlite3.connect(a.out)
    for (t,) in db.execute("select name from sqlite_master where type='table'").fetchall():
        if t != "VERSION_TABLE": db.execute(f'delete from "{t}"')

    media = []
    mid = 0
    for k in files:
        tg = tags[k]
        if not tg["ok"]: continue
        mid += 1
        ext = k.rsplit(".", 1)[1].lower()
        size = mt[k][1]
        parts = k.split("/")
        stem = parts[-1].rsplit(".", 1)[0]
        name = tg["title"] or re.sub(r"^\d+\s*-\s*", "", stem)
        album = tg["album"] or re.sub(r"^\d{4}\s*-\s*", "", parts[-2])
        artist = tg["artist"] or parts[1]
        if ext == "opus":
            ms = round(tg["raw_len"] * 1000)   # HiBy rechnet mit Millisekunden
            br = int(size * 8 * 1000 / ms) if ms else 0
        else:
            br = tg["br"]
        ctime = ct.get(k, (0, 0, 0))[2]
        mtime = mt.get("/".join(parts[:-1]), (0, 0, 0))[2]
        path = "a:\\" + k.replace("/", "\\")
        media.append(dict(id=mid, path=path, name=name, album=album, artist=artist, genre=tg["genre"].encode()[:127].decode("utf-8", "ignore"),   # HiBy-Puffer 128 Byte
                          year=tg["year"], dis=tg["disc"], ck=tg["trk"], size=size, sr=tg["sr"], br=br,
                          ch=tg["ch"], fmt=AUDIO[ext], ctime=ctime, mtime=mtime, aa=tg["aa"]))

    db.executemany("""insert into MEDIA_TABLE (id,path,name,album,artist,genre,year,dis_id,ck_id,has_child_file,
        begin_time,end_time,cue_id,character,size,sample_rate,bit_rate,bit,channel,format,quality,album_pic_path,
        lrc_path,track_gain,track_peak,ctime,mtime,pinyin_charater,album_artist)
        values (?,?,?,?,?,?,?,?,?,0,0,-1,-1,?,?,?,?,16,?,?,'0',?,?,NULL,NULL,?,?,?,?)""",
        [(m["id"], Z(m["path"]), Z(m["name"]), Z(m["album"]), Z(m["artist"]), Z(m["genre"]), m["year"], m["dis"], m["ck"],
          first_char(m["name"]), m["size"], m["sr"], m["br"], m["ch"], m["fmt"], Z(""), Z(""), m["ctime"], m["mtime"],
          pinyin(m["name"]), Z(m["aa"])) for m in media])

    def groups(key):
        """wie SQLite COLLATE NOCASE: ASCII-Groß/Klein egal; Anzeige = erste Schreibweise"""
        g = collections.OrderedDict(); first = {}
        for m in media:
            v = m[key]; k = upper_ascii(v) if isinstance(v, str) else v
            first.setdefault(k, v)
            g.setdefault(first[k], []).append(m)
        return g

    albums = groups("album")
    db.executemany("insert into ALBUM_TABLE (id,album,character,cn,ctime,mtime,mqa,pinyin_charater) values (?,?,?,?,?,?,0,?)",
        [(L[0]["id"], Z(k), first_char(k), len(L), L[0]["ctime"], L[0]["mtime"], pinyin(k)) for k, L in albums.items()])
    arts = groups("artist")
    def art_cn(L):
        n = len({m["album"] for m in L})
        return min(n, 3) if n >= 2 else len(L)   # Bedeutung unklar; passt zur Vorlage
    db.executemany("insert into ARTIST_TABLE (id,artist,character,cn,ctime,mtime,pinyin_charater) values (?,?,?,?,?,?,?)",
        [(L[0]["id"], Z(k), first_char(k), art_cn(L), L[0]["ctime"], L[0]["mtime"], pinyin(k)) for k, L in arts.items()])
    aas = groups("aa")
    db.executemany("insert into ALBUM_ARTIST_TABLE (id,album_artist,character,cn,ctime,mtime,mqa,pinyin_charater) values (?,?,?,1,?,?,0,?)",
        [(L[0]["id"], Z(k), first_char(k), L[0]["ctime"], L[0]["mtime"], pinyin(k)) for k, L in aas.items() if k])
    gens = groups("genre")
    db.executemany("insert into GENRE_TABLE (id,genre,character,cn,ctime,mtime,pinyin_charater) values (?,?,?,?,?,?,?)",
        [(L[0]["id"], Z(k), first_char(k), len(L), L[0]["ctime"], L[0]["mtime"], pinyin(k)) for k, L in gens.items() if k])
    fm = groups("fmt")
    for tbl in ("FORMAT_TABLE", "FORMAT2_TABLE"):
        db.executemany(f"insert into {tbl} (id,format,character,cn) values (?,?,?,1)",
            [(L[0]["id"], FMTNAME[k], FMTNAME[k][0]) for k, L in fm.items()])
    db.executemany("insert into CTIME_TABLE (media_id) values (?)",
        [(m["id"],) for m in sorted(media, key=lambda m: (m["ctime"], m["id"]))])
    db.executemany("insert into MTIME_TABLE (media_id) values (?)",
        [(m["id"],) for m in sorted(media, key=lambda m: (m["mtime"], m["id"]))])
    n_aa = sum(1 for k in aas if k); n_g = sum(1 for k in gens if k)
    db.executemany("insert into COUNT_TABLE (cn) values (?)", [(len(media),), (len(albums),), (len(arts),), (n_g,), (n_aa,)])
    db.commit(); db.execute("vacuum"); db.close()
    print(f"fertig: {len(media)} Lieder, {len(albums)} Alben, {len(arts)} Interpreten, {n_g} Genres", file=sys.stderr)

if __name__ == "__main__":
    main()
