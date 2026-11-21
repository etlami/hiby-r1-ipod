# HiBy R1 as an iPod for the car

Turns a **HiBy R1** music player into something a car stereo accepts as an **iPod on its USB port** —
with sound over USB, track info on the head-unit display and **steering-wheel controls** (next/previous).

Built for a 2015 Nissan NV200 whose stock radio only speaks the old iPod protocol (iAP1): an iPhone
gets "accessory not supported", an AUX cable loses the steering-wheel buttons. The R1 runs Linux
(Ingenic X1600, kernel 4.4.94), so it can pretend to be an iPod.

> **Status:** works daily in the car — 120k+ songs on a 512 GB card, music, display and steering wheel.
> Only one car tested. Unofficial, use at your own risk. You need the bidhata mod (root + boot menu).

## What it does

```
 HiBy player ──PCM──► pcmshim.so (LD_PRELOAD) ──FIFO──► aplay ──► iPod USB audio ─┐
                                                                                  ├─► car stereo
 iPod client (Go, iAP1) ◄──── /dev/iap0 (HID) ◄──── g_ipod_gadget (kernel) ───────┘
      │  now playing: reads the open audio file of hiby_player (tags + duration)
      └─ steering wheel: PlayControl next/prev → key events into the player
```

- **USB gadget**: [oandrew/ipod-gadget](https://github.com/oandrew/ipod-gadget) kernel modules, built for the
  R1's 4.4 kernel. The car sees an "Apple iPhone" (05ac:12a8) with HID (iAP) + USB audio.
- **iAP client**: [oandrew/ipod](https://github.com/oandrew/ipod) with
  [bensonjohnson's](https://github.com/bensonjohnson/iap-usb-gadget) Volvo fixes plus our head-unit fixes.
- **Audio**: `hiby_player` writes to `/dev/snd/pcmC0D0p` directly (no ALSA lib). `pcmshim.so` hooks
  `open/ioctl`, copies every frame into a FIFO, and `loopbridge.sh` plays it into the iPod sound card
  while the car is connected. The player keeps playing on its own codec (clock master).
- **Controls**: the client injects `KEY_NEXTSONG`/`KEY_PREVIOUSSONG` into the player's input devices.
- **Display**: title/artist/album/position of the track `hiby_player` currently has open.
- **Boot menu**: "HIBY PLAYER + IPOD" is the default entry (countdown), plain "HIBY PLAYER" stays available
  (needed for USB-C headphones — in iPod mode USB is taken by the gadget).

## Things we had to figure out (head-unit side)

The radio enumerated the fake iPod and then power-cycled the USB port every ~4.6 s. Fixes, in order of impact:

1. **Remember repeat/shuffle.** The radio sends `SetRepeat(All)` and checks it with `GetRepeat`. Answering
   "off" made it reset the port. This was the main cause.
2. **No transaction IDs** when the accessory speaks old iAP without them (it never sends any).
3. **Authentication**: signature request with counter 1 and a random challenge. The radio needs ~50 s to
   answer — that is normal, don't time out.
4. **Audio negotiation** (`GetAccSampleRateCaps` → `TrackNewAudioAttributes` 44.1 kHz) after the last
   certificate part and again after the signature.
5. **`PlayStatusChangeNotification` every second** (position in ms), otherwise the clock on the display stands still.
6. **Start paused** until the radio sends `PlayControl` — otherwise display works but audio stays muted.
7. Kernel 4.4: `composite_setup` only calls `req_match` once a configuration is set, so Apple's vendor
   request `0x40` (charging) **before** `SET_CONFIGURATION` got stalled. The gadget patch answers it itself.

Not the cause (tested): over-current/charging limit, high-speed vs. full-speed, 64-byte HID reports.

## Things we had to figure out (player side)

- **Frozen screen with a big library.** `hiby_player` needs 6 MB of contiguous DMA memory for the display
  (order-11 allocation on a 64 MB device) but only opens `/dev/sa_hgl_dma` *after* loading the database —
  by then memory is fragmented. `pcmshim` opens the device in its constructor and hands the fd over on
  the player's first `open()`. (Off switch: `touch /usr/data/hgl_prealloc_off`.)
- **Database too big for internal flash.** `/usr/data` (45 MB) fits ~20k songs. `hibydb.sh` bind-mounts
  `.hiby/usrlocal_media.db` from the SD card over the internal file (the player deletes symlinks).
- **Scanning 120k songs on the device takes forever** → [`tools/hibydb`](tools/hibydb/build_hibydb.py)
  builds the player database on a PC from a card listing (`ls -lR --full-time` via ADB, for ctime/mtime)
  plus the tags of a server copy of the music. Format details (NUL terminators, pinyin sort keys, IDs in
  path order) are documented in the script. It needs a small real database from the device as template
  (`--vorlage`: scan a few albums on the device, pull `/usr/data/usrlocal_media.db`).
- The menu's countdown returns exit code 0 → the launcher would start the bare player. The wrapper
  `bidhata-menu-wrapper.sh` maps that to our start script.
- `overcommit_memory=1`, otherwise the Go client segfaults at start when the player holds a lot of RAM.

## Requirements

- HiBy R1 with firmware 2.0 and the [bidhata/Hiby-R1-Mod](https://github.com/bidhata/Hiby-R1-Mod) (2.0)
- A car stereo that speaks iAP1 **without** an Apple authentication chip (most 2008–2015 head units
  with "iPod" on the USB port)
- For building: the Ingenic X1600 kernel SDK `ingenic-linux-kernel4.4.94-x1600-v6.0-20240606`
  (Ingenic's public FTP, see [Jepl4r/hiby-custom-kernel](https://github.com/Jepl4r/hiby-custom-kernel)),
  a clone of `hiby-custom-kernel`, Go, git. Linux x86-64 host (we used a Debian container).

## Build

```sh
SDK=/path/to/ingenic-linux-kernel4.4.94-x1600-v6.0-20240606 KIT=/path/to/hiby-custom-kernel \
  SRC=/path/to/ksrc build/prep_kernel.sh     # kernel tree matching the stock vermagic "4.4.94+"
build/fetch.sh                               # upstream sources + Benson's patches + ours
SDK=... SRC=... build/build.sh               # -> build/out/{g_ipod_*.ko, ipod.bin, pcmshim.so}
```

`build.sh client` alone needs only Go.

## Install

1. Boot menu → UTILITIES → ENABLE ADB, stay in the menu, connect USB.
2. `build/install.sh` pushes modules, client, shim and scripts to `/usr/data`.
3. Put the rows from [`device/menu-rows.conf`](device/menu-rows.conf) at the top of
   `/usr/data/bidhata-menu.conf` (replacing the old "HIBY PLAYER" row).
4. Reboot. "HIBY PLAYER + IPOD" starts after the countdown.

Debugging a new car: [`tools/debug/modtest.sh`](tools/debug/modtest.sh) loads the gadget, records an
iAP trace and plays a test tone, logs go to the SD card (`modtest_HHMMSS/`). Client switches:
`IPOD_START_PAUSED`, `IPOD_NO_BLUEZ` (always set on the HiBy), `IPOD_NO_SIG`, `IPOD_NO_R4`.

## Repository layout

| Path | Content |
|---|---|
| `patches/ipod-hiby.patch` | iAP client: head-unit fixes, now-playing from `hiby_player`, key injection |
| `patches/ipod-gadget-hiby.patch` | kernel 4.4 compatibility, Apple `0x40` request before configuration |
| `pcmshim/` | `LD_PRELOAD` shim: audio tap + display-DMA preallocation |
| `device/` | start scripts, database bind mount, audio bridge, menu wrapper |
| `build/` | kernel prep, fetch, build, install |
| `tools/hibydb/` | build the HiBy music database off-device |
| `tools/playlists/` | album-by-album and genre playlists ([notes on the m3u format](tools/playlists/README.md)) |

Code comments are mostly German.

## Credits

- [oandrew/ipod](https://github.com/oandrew/ipod) and [oandrew/ipod-gadget](https://github.com/oandrew/ipod-gadget) (MIT) — the foundation
- [bensonjohnson/iap-usb-gadget](https://github.com/bensonjohnson/iap-usb-gadget) — the Volvo fixes that proved this works in a car; his patches are fetched from his repo, not included here
- [bidhata/Hiby-R1-Mod](https://github.com/bidhata/Hiby-R1-Mod) — root access and the boot menu
- [Jepl4r/hiby-custom-kernel](https://github.com/Jepl4r/hiby-custom-kernel) — kernel config for the R1
- [mojyack/libiap](https://github.com/mojyack/libiap) and the Rockbox iAP head-unit issues — reference for authentication details

## License

MIT for everything in this repository (see [LICENSE](LICENSE)). The upstream projects keep their own licenses.
