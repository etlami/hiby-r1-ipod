#!/bin/sh
# Musik-Datenbank des HiBy auf die SD-Karte legen.
# Der interne Speicher (/usr/data, 45 MB) fasst nur ~20.000 Lieder; die Karte
# hat Platz. Der Player benutzt fest /usr/data/usrlocal_media.db und löscht
# Symlinks -> Bind-Mount der Karten-Datei über die interne Datei.
# Abschalten: touch /usr/data/hibydb_off
export PATH=/sbin:/usr/sbin:/bin:/usr/bin:$PATH
SD=/usr/data/mnt/sd_0   # /data ist Symlink; /proc/mounts zeigt den echten Pfad
INT=/usr/data/usrlocal_media.db
DIR=$SD/.hiby
EXT=$DIR/usrlocal_media.db
LOG=/usr/data/hibydb.log   # intern, klein, überlebt Neustart

log() { echo "$(date '+%F %T') $*" >> $LOG; [ -d $DIR ] && echo "$(date '+%F %T') $*" >> $DIR/hibydb.log; }
[ -f $LOG ] && [ $(wc -c < $LOG) -gt 20000 ] && tail -50 $LOG > $LOG.x && mv $LOG.x $LOG

[ -f /usr/data/hibydb_off ] && { log "abgeschaltet (hibydb_off)"; exit 0; }
grep -q " $INT " /proc/mounts && { log "schon eingehängt"; exit 0; }
# Karte selbst einbinden, falls noch nicht geschehen (wie der Launcher; wartet auf mmcblk)
if ! grep -q " $SD " /proc/mounts; then
    mkdir -p /data/mnt/sd_0
    i=0; while [ $i -lt 50 ] && [ ! -b /dev/mmcblk0p1 ] && [ ! -b /dev/mmcblk0 ]; do sleep 0.1; i=$((i+1)); done
    for dev in /dev/mmcblk0p1 /dev/mmcblk0 /dev/mmcblk1p1 /dev/mmcblk1; do
        [ -b $dev ] || continue
        mount -t exfat $dev /data/mnt/sd_0 2>/dev/null || mount $dev /data/mnt/sd_0 2>/dev/null || continue
        log "SD selbst eingehängt: $dev"; break
    done
fi
grep -q " $SD " /proc/mounts || { log "SD nicht eingehängt, DB bleibt intern"; exit 0; }

mkdir -p $DIR || { log "kann $DIR nicht anlegen"; exit 0; }
[ -f $EXT ] || { : > $EXT; log "neue leere DB auf der Karte angelegt"; }

# interne Datei/Symlink durch leeren Platzhalter ersetzen
rm -f $INT $INT-journal $INT-wal $INT-shm
: > $INT
if mount --bind $EXT $INT; then
    log "DB eingehängt: $EXT ($(ls -l $EXT | awk '{print $5}') Bytes)"
else
    log "bind-mount fehlgeschlagen"
fi
