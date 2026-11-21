import re
def _num(p):
    fn = p.rstrip('\x00').rsplit('\\', 1)[1]
    m = re.match(r'(?:(\d+)-)?(\d+) - (.*)\.\w+$', fn)
    return (int(m.group(1) or 1), int(m.group(2)), m.group(3)) if m else None
def complete(paths):
    """Album vollständig genug: >= 5 Lieder, je CD >= 80 % der Tracknummern vorhanden, Track 1 dabei."""
    n = [x for x in map(_num, paths) if x]
    if len(paths) < 5 or not n: return False
    discs = {}
    for d, t, _ in n: discs.setdefault(d, set()).add(t)
    ok = lambda ts: 1 in ts and len(ts) >= 0.8 * max(ts)
    return 1 in discs and ok(discs[1])      # CD 1 zählt; lückenhafte Bonus-CDs fliegen in clean_tracks raus
def clean_tracks(paths):
    """Sortiert; doppelte Fassungen (mono/stereo, Remaster) nur einmal."""
    discs = {}
    for x in filter(None, map(_num, paths)): discs.setdefault(x[0], set()).add(x[1])
    good = {d for d, ts in discs.items() if 1 in ts and len(ts) >= 0.8 * max(ts)}
    seen = set(); out = []
    for p in sorted(paths):
        x = _num(p); t = x[2] if x else p
        if x and x[0] not in good: continue
        key = re.sub(r'\s*[\(\[][^)\]]*(mono|stereo|remaster|version|mix)[^)\]]*[\)\]]', '', t, flags=re.I).lower()
        key = re.sub(r'[^a-z0-9]', '', key)
        if key in seen: continue
        seen.add(key); out.append(p)
    return out
