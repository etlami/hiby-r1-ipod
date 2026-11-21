# Playlists for the HiBy (examples)

The HiBy picks up `.m3u` files from the card folder `Playlists/` without a rescan. What works:

- `#EXTM3U` as the first line, CRLF line endings, UTF-8
- **absolute paths in HiBy notation**: `a:\Music\Artist\Album\01 - Title.opus` (sound + cover art)
- `../Music/...` is listed but does not play; `\Music\...` does not work at all
- 20,000+ entries per playlist are fine

The scripts read track paths straight from the HiBy database (`HIBY_DB=usrlocal_media.db`).

| Script | Purpose | Inputs |
|---|---|---|
| `match.py` | matches canon album lists against the albums on the card | `spreadsheet.csv` from [seanbreckenridge/albums](https://github.com/seanbreckenridge/albums), `acclaimed.json` (Acclaimed Music Top 3000) |
| `build.py` | "Top 250": critics + Last.fm plays + personal taste | `matches.json`, `plan.csv`, `seeds.json` (your own data) |
| `gen.py` | writes album-by-album playlists; `common.py` drops incomplete albums and mono/stereo duplicates | — |
| `eurodance.py` | genre playlists from an artist list: "Hits" (Last.fm top 10 per artist) and "Alles" (every song once, original before radio edit before remix) | `ed_top.json` (Last.fm `artist.getTopTracks`) |

They are tailored to my library layout (`Artist/Year - Album/NN - Title.opus`) — use them as a starting point.
