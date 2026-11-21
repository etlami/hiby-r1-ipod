#!/bin/sh
# Normaler HiBy-Player, aber mit Musik-Datenbank auf der SD-Karte
/usr/data/hibydb.sh
killall hiby_player >/dev/null 2>&1; killall -9 hiby_player >/dev/null 2>&1
# Player braucht 8 MB am Stück (DMA fürs Display): Cache leeren + Speicher kompaktieren
sync; echo 3 > /proc/sys/vm/drop_caches; [ -e /proc/sys/vm/compact_memory ] && echo 1 > /proc/sys/vm/compact_memory
LD_PRELOAD=/usr/data/pcmshim.so /usr/bin/hiby_player   # Shim reserviert den Grafik-DMA vorab
sleep 1; reboot
