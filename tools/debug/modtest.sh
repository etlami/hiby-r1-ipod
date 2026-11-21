#!/bin/sh
# Diagnose für neue Autoradios: lädt die Module, startet den iPod-Client mit iAP-Trace und spielt
# einen Testton (/usr/data/tone.wav, 44,1 kHz WAV). Logs landen auf der SD-Karte (modtest_HHMMSS/).
# Nutzung: modtest.sh DAUER_S [adb]   (adb = danach ADB wieder einschalten)   env IPOD_ARGS = Modulparameter
SD=/usr/data/mnt/sd_0
OUT=$SD/modtest_$(date +%H%M%S); mkdir -p $OUT
exec >$OUT/ablauf.log 2>&1
G=/sys/kernel/config/usb_gadget
DUR=${1:-60}
echo "start $(date) dauer=$DUR"
[ -d $G ] || mount -t configfs none /sys/kernel/config
for p in $(ps | grep -E "adbserver.sh|adbd" | grep -v grep | awk '{print $1}'); do kill $p; done
sleep 1; killall -9 adbd 2>/dev/null
/usr/bin/usb_dev_mass_storage.sh stop /dev/mmcblk0 >/dev/null 2>&1
for u in $G/*/UDC; do [ -n "$(cat $u 2>/dev/null)" ] && echo "loese $u" && echo "" > $u; done
umount /dev/usb-ffs/adb 2>/dev/null
dmesg -c >/dev/null
# Strom/USB-Zustand sekündlich mitschreiben
PS=/sys/class/power_supply
( while true; do
    echo "$(date +%T) usb_on=$(cat $PS/usb/online) ac_on=$(cat $PS/ac/online) udc=$(cat /sys/class/udc/*/state)"
    sleep 1
  done ) > $OUT/strom.log 2>&1 &
PW=$!
lsmod | grep -q g_ipod_hid || insmod /usr/data/g_ipod_hid.ko
lsmod | grep -q g_ipod_audio || insmod /usr/data/g_ipod_audio.ko
insmod /usr/data/g_ipod_gadget.ko $IPOD_ARGS; echo "gadget rc=$?"
i=0; while [ ! -c /dev/iap0 ] && [ $i -lt 20 ]; do sleep 0.5; i=$((i+1)); done
ls -l /dev/iap0
n=0
IPOD_NO_BLUEZ=1 /usr/data/ipod -d serve -w $OUT/trace_$n.bin /dev/iap0 > $OUT/ipod_$n.log 2>&1 &
IP=$!
# Testton in die iPod-Soundkarte, sobald das Radio konfiguriert hat (Endlosschleife)
( while true; do
    if [ "$(cat /sys/class/udc/*/state 2>/dev/null)" = "configured" ]; then
      aplay -q -D plughw:CARD=iPodUSB,DEV=0 /usr/data/tone.wav >> $OUT/aplay.log 2>&1 || sleep 1
    else sleep 1; fi
  done ) &
AP=$!
i=0; last=""
while [ $i -lt $DUR ]; do
  st=$(cat /sys/class/udc/*/state 2>/dev/null)
  [ "$st" != "$last" ] && echo "t=$i usb-state=$st" && last=$st
  if ! kill -0 $IP 2>/dev/null; then   # ipod beendet -> neu starten, eigenes Log
    echo "t=$i ipod beendet, Neustart"; n=$((n+1))
    IPOD_NO_BLUEZ=1 /usr/data/ipod -d serve -w $OUT/trace_$n.bin /dev/iap0 > $OUT/ipod_$n.log 2>&1 &
    IP=$!
  fi
  sleep 1; i=$((i+1))
done
kill $IP $AP $PW; killall aplay 2>/dev/null; sleep 1; killall -9 ipod 2>/dev/null
echo "--- dmesg"; dmesg | grep -vE "android_work|uevent"
rmmod g_ipod_gadget; echo "rmmod rc=$?"
if [ "$2" = "adb" ]; then
  setsid /sbin/adbserver.sh 440 </dev/null >/dev/null 2>&1 &
  sleep 3
  [ -z "$(cat $G/adb_demo/UDC)" ] && echo 13500000.otg_new > $G/adb_demo/UDC
  echo "adb UDC: [$(cat $G/adb_demo/UDC)]"
fi
echo "ende $(date)"; sync
