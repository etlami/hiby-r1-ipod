#!/bin/bash
# Kernelbaum für externe Module, passend zum Stock-R1-Kernel (nach hiby-custom-kernel/build.sh)
set -e
SDK=${SDK:-/root/sdk/ingenic-linux-kernel4.4.94-x1600-v6.0-20240606}   # Ingenic-X1600-SDK (siehe README)
KIT=${KIT:-/root/hiby-custom-kernel}                                  # Klon von Jepl4r/hiby-custom-kernel
export PATH=$SDK/prebuilts/toolchains/mips-gcc720-glibc229/bin:$PATH
SRC=${SRC:-/root/ksrc}
rm -rf $SRC; cp -a $SDK/kernel/kernel-4.4.94 $SRC; cd $SRC
MK=(make ARCH=mips CROSS_COMPILE=mips-linux-gnu- "HOSTCC=gcc -fcommon")
"${MK[@]}" mrproper >/dev/null
printf '+\n' > .scmversion
for p in $KIT/patches/0*.patch; do echo "patch $(basename $p)"; patch -p1 -s < $p; done
"${MK[@]}" x1600_halley6_module_base_linux_sfc_nand_defconfig >/dev/null
"${MK[@]}" olddefconfig >/dev/null
./scripts/kconfig/merge_config.sh -m -O . .config $KIT/configs/r1-required.config $KIT/configs/r1-parity.config | grep -E "^(WARNING|warning)" || true
# wie Stock: configfs-HID an
./scripts/kconfig/merge_config.sh -m -O . .config <(printf 'CONFIG_USB_CONFIGFS_F_HID=y\nCONFIG_USB_F_HID=y\n') >/dev/null
"${MK[@]}" olddefconfig >/dev/null
for o in PREEMPT MODULE_UNLOAD CPU_MIPS32_R2 32BIT USB_LIBCOMPOSITE USB_CONFIGFS USB_CONFIGFS_F_HID SND; do printf '%s: ' $o; grep -E "^CONFIG_$o=" .config || echo FEHLT; done
grep -q "^CONFIG_MODVERSIONS=y" .config && echo "WARNUNG MODVERSIONS an" || echo "MODVERSIONS aus (gut)"
"${MK[@]}" -j8 modules_prepare 2>&1 | tail -3
echo "kernelrelease: $("${MK[@]}" -s kernelrelease)"
grep UTS_RELEASE include/generated/utsrelease.h
