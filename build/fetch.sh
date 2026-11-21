#!/bin/bash
# Holt die Upstream-Quellen in festen Ständen und spielt die Patches ein:
#   1. oandrew/ipod + oandrew/ipod-gadget (MIT)
#   2. Bensons Volvo-Fixes (bensonjohnson/iap-usb-gadget) – nicht in diesem Repo enthalten
#   3. unsere HiBy-Patches (patches/)
set -e
cd "$(dirname "$0")"; ROOT=$(cd .. && pwd); mkdir -p src; cd src
IPOD=3762132cc9ad94c5301dddb9365a923350e0020f
GADGET=ece6b7b0b29dacb7be0cf9f6436fc390892969e8
BENSON=5beb7169f49c8bbc8a39f1e6191b308773a89e09
get() { [ -d "$1" ] || git clone -q "$2" "$1"; git -C "$1" checkout -q -f "$3"; git -C "$1" clean -qfdx; }
get ipod https://github.com/oandrew/ipod.git $IPOD
get ipod-gadget https://github.com/oandrew/ipod-gadget.git $GADGET
get benson https://github.com/bensonjohnson/iap-usb-gadget.git $BENSON
BP=benson/archive/rpi-zero/patches
git -C ipod apply ../$BP/ipod-volvo-fixes.patch
git -C ipod apply "$ROOT/patches/ipod-hiby.patch"
git -C ipod-gadget apply ../$BP/ipod-gadget-apple-strings.patch ../$BP/ipod-gadget-audio-rate-fix.patch
git -C ipod-gadget apply "$ROOT/patches/ipod-gadget-hiby.patch"
echo "Quellen bereit in build/src/"
