#!/bin/sh
# HiBy-Player mit iPod-Modus: Gadget laden, iPod-Client im Hintergrund, Player-Ton per pcmshim
# auf die iPod-USB-Karte umleiten, solange das Radio verbunden ist.
export PATH=/sbin:/usr/sbin:/bin:/usr/bin:$PATH
LOG=/tmp/ipodplayer.log
exec >$LOG 2>&1
echo "start $(date)"
# Go-Client braucht Overcommit, sonst Segfault beim Start, wenn der Player viel RAM belegt
echo 1 > /proc/sys/vm/overcommit_memory
G=/sys/kernel/config/usb_gadget
[ -d $G ] || mount -t configfs none /sys/kernel/config
for p in $(ps | grep -E "adbserver.sh|adbd" | grep -v grep | awk '{print $1}'); do kill $p; done
sleep 1; killall -9 adbd 2>/dev/null
/usr/bin/usb_dev_mass_storage.sh stop /dev/mmcblk0 >/dev/null 2>&1
for u in $G/*/UDC; do [ -n "$(cat $u 2>/dev/null)" ] && echo "" > $u; done
umount /dev/usb-ffs/adb 2>/dev/null
lsmod | grep -q g_ipod_hid || insmod /usr/data/g_ipod_hid.ko
lsmod | grep -q g_ipod_audio || insmod /usr/data/g_ipod_audio.ko
lsmod | grep -q g_ipod_gadget || insmod /usr/data/g_ipod_gadget.ko product_id=0x12a8 only_ipod=1
echo "gadget rc=$?"
# Dienste erst NACH dem Player-Start: Der Player braucht beim Start 8 MB DMA am Stück
# (Display); laufen WLAN/Go-Programme schon vorher, ist der Speicher zersplittert -> Bild friert.
dienste() {
  # iPod-Client mit Neustart-Schleife
  ( while true; do
      i=0; while [ ! -c /dev/iap0 ] && [ $i -lt 20 ]; do sleep 0.5; i=$((i+1)); done
      IPOD_NO_BLUEZ=1 /usr/data/ipod serve /dev/iap0 > /tmp/ipod_client.log 2>&1
      echo "ipod-client beendet $(date)"; sleep 1
    done ) &
  # Ton-Abgriff (pcmshim) -> FIFO -> loopbridge.sh -> iPod-USB-Karte
  setsid /usr/data/loopbridge.sh </dev/null >/dev/null 2>&1 &
}
( i=0; while ! pidof hiby_player >/dev/null && [ $i -lt 60 ]; do sleep 0.5; i=$((i+1)); done
  sleep 6; dienste ) &
# Player wie der Launcher, aber mit Umleitung
touch /tmp/ipod_mode   # pcmshim prüft das beim Öffnen des Audiogeräts
/usr/data/hibydb.sh
killall hiby_player >/dev/null 2>&1; killall -9 hiby_player >/dev/null 2>&1
# Player braucht 8 MB am Stück (DMA fürs Display): Cache leeren + Speicher kompaktieren
sync; echo 3 > /proc/sys/vm/drop_caches; [ -e /proc/sys/vm/compact_memory ] && echo 1 > /proc/sys/vm/compact_memory
LD_PRELOAD=/usr/data/pcmshim.so /usr/bin/hiby_player
sleep 1
reboot
