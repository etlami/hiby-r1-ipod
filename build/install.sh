#!/bin/sh
# Spielt alles per ADB auf den HiBy R1 (bidhata-Mod, Bootmenü -> UTILITIES -> ENABLE ADB, im Menü bleiben).
set -e
cd "$(dirname "$0")"; ROOT=$(cd .. && pwd)
adb get-state >/dev/null
for f in out/g_ipod_hid.ko out/g_ipod_audio.ko out/g_ipod_gadget.ko out/ipod.bin out/pcmshim.so; do
  adb push "$f" /usr/data/
done
for f in ipod ipodplayer.sh hibyplayer.sh hibydb.sh loopbridge.sh; do adb push "$ROOT/device/$f" /usr/data/; done
adb push "$ROOT/device/bidhata-menu-wrapper.sh" /usr/data/bidhata-menu
adb shell 'cd /usr/data && chmod +x ipod ipod.bin ipodplayer.sh hibyplayer.sh hibydb.sh loopbridge.sh bidhata-menu'
echo "Fertig. Jetzt die Zeilen aus device/menu-rows.conf in /usr/data/bidhata-menu.conf eintragen (siehe README)."
