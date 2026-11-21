#!/bin/bash
# Baut alles fürs Gerät nach build/out/:
#   g_ipod_*.ko  (Kernelmodule, brauchen SDK + vorbereiteten Kernelbaum, siehe prep_kernel.sh)
#   ipod.bin     (iPod-Client, Go)
#   pcmshim.so   (LD_PRELOAD-Shim für den HiBy-Player)
# Teile einzeln: build.sh [modules] [client] [shim]   (ohne Argument: alle)
set -e
cd "$(dirname "$0")"; ROOT=$(cd .. && pwd); OUT=$PWD/out; mkdir -p "$OUT"
SDK=${SDK:-/root/sdk/ingenic-linux-kernel4.4.94-x1600-v6.0-20240606}
SRC=${SRC:-/root/ksrc}
export PATH=$SDK/prebuilts/toolchains/mips-gcc720-glibc229/bin:$PATH
WHAT=${*:-modules client shim}
[ -d src/ipod ] || ./fetch.sh
for w in $WHAT; do case $w in
  modules)
    make -C "$SRC" ARCH=mips CROSS_COMPILE=mips-linux-gnu- "HOSTCC=gcc -fcommon" M=$PWD/src/ipod-gadget/gadget clean modules
    cp src/ipod-gadget/gadget/g_ipod_*.ko "$OUT/" ;;
  client)
    (cd src/ipod && CGO_ENABLED=0 GOOS=linux GOARCH=mipsle GOMIPS=softfloat GOFLAGS=-mod=mod \
       go build -trimpath -ldflags="-s -w" -o "$OUT/ipod.bin" ./cmd/ipod) ;;
  shim)
    mips-linux-gnu-gcc -EL -mips32r2 -O2 -Wall -fPIC -shared -o "$OUT/pcmshim.so" "$ROOT/pcmshim/pcmshim.c" -ldl ;;
  *) echo "unbekannt: $w"; exit 1 ;;
esac; done
ls -l "$OUT"
