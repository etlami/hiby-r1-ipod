#!/bin/sh
# Reicht den vom pcmshim abgegriffenen Player-Ton (FIFO) an die iPod-USB-Karte weiter,
# solange das Radio verbunden ist. Format/Rate/Kanaele stehen in /tmp/loop_play.
LOG=/tmp/loopbridge.log
FIFO=/tmp/ipod.fifo
[ -p $FIFO ] || { rm -f $FIFO; mkfifo $FIFO; }
verbunden() { [ "$(cat /sys/class/udc/*/state 2>/dev/null)" = "configured" ]; }
stop_kette() { killall aplay 2>/dev/null; }
last=""; laeuft=0
while true; do
  info=$(cat /tmp/loop_play 2>/dev/null)
  if [ -n "$info" ] && verbunden; then
    if [ "$info" != "$last" ] || ! pidof aplay >/dev/null; then
      stop_kette; sleep 0.1
      set -- $info
      chrt -f 60 aplay -q -t raw -f $1 -r $2 -c $3 -D plughw:CARD=iPodUSB,DEV=0 -B 300000 < $FIFO 2>>$LOG &
      echo "$(date +%T) ipod <- $1 $2 Hz $3 ch" >> $LOG
      last=$info; laeuft=1
    fi
  else
    [ $laeuft = 1 ] && { stop_kette; laeuft=0; last=""; echo "$(date +%T) gestoppt" >> $LOG; }
  fi
  sleep 0.5
done
