#!/bin/sh
# Vorschalter fürs Bootmenü (Launcher nimmt /usr/data/bidhata-menu bevorzugt).
# Das echte Menü liefert bei Ablauf des 3-s-Countdowns Status 0 (bzw. 10 = Player-Zeile) -> nackter Player.
# Wir machen daraus "HIBY PLAYER + IPOD" (Status 42 + Ziel), damit Datenbank-
# Umleitung, iPod-Modus und Debug-Zugang auch ohne Antippen laufen.
/usr/bin/bidhata-menu
rc=$?
echo "$(date '+%F %T') menu rc=$rc" >> /usr/data/menu.log
if { [ "$rc" -eq 10 ] || [ "$rc" -eq 0 ]; } && [ -x /usr/data/ipodplayer.sh ]; then
    echo /usr/data/ipodplayer.sh > /usr/data/bidhata_exec_target
    exit 42
fi
exit $rc
