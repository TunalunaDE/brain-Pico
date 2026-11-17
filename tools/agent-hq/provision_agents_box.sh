#!/bin/sh
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# provision_agents_box.sh - first setup of the noknok agents box (Ubuntu). Run as root:
#   sudo sh provision_agents_box.sh
# Writes /home/agents/provision.log. Safe to run again (every step checks first).
# 7-bit ASCII only.

LOG=/home/agents/provision.log
exec >>"$LOG" 2>&1
echo "== start $(date)"
export DEBIAN_FRONTEND=noninteractive

timedatectl set-timezone Europe/Zurich
apt-get update

# One package at a time: a missing package must not abort the rest.
CORE="build-essential git curl wget unzip jq rsync ripgrep tmux htop usbutils pkg-config
libusb-1.0-0-dev libudev-dev python3-pip python3-venv python3-serial python3-requests python3-pytest
openocd gdb-multiarch gcc-riscv64-unknown-elf libnewlib-dev uhubctl android-tools-adb picotool
socat netcat-openbsd iperf3 iw ethtool tcpdump i2c-tools"
for p in $CORE; do
  apt-get install -y "$p" || echo "PKGFAIL $p"
done

# USB access for the bench tools (WCH-LinkE, Pico, Debug Probe, CircuitPython, FTDI serial)
cat >/etc/udev/rules.d/99-noknok.rules <<'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="2e8a", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="239a", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0403", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", MODE="0666", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", MODE="0666", GROUP="dialout"
EOF
udevadm control --reload-rules
udevadm trigger
usermod -aG dialout,plugdev agents

# background jobs of the agents survive logout; never suspend
loginctl enable-linger agents
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

# folders (same shape as the Pis: ~/dev/..., plus an archive for rig logs)
for d in dev archive archive/noknok archive/Pi4RFID logs; do
  mkdir -p /home/agents/$d
done
chown -R agents:agents /home/agents/dev /home/agents/archive /home/agents/logs

# ch32fun + minichlink (same layout as on the Pis: ~/dev/ch32fun/{ch32fun,minichlink})
if [ ! -d /home/agents/dev/ch32fun ]; then
  sudo -u agents -H git clone https://github.com/cnlohr/ch32fun /home/agents/dev/ch32fun
fi
if [ -d /home/agents/dev/ch32fun/minichlink ]; then
  sudo -u agents -H make -C /home/agents/dev/ch32fun/minichlink || echo "MAKEFAIL minichlink"
fi

echo "== versions"
uname -a
for t in git python3 pip3 openocd uhubctl adb picotool riscv64-unknown-elf-gcc gdb-multiarch; do
  printf "%s: " "$t"
  ( "$t" --version 2>&1 | head -1 ) || echo "missing"
done
( cd /home/agents/dev/ch32fun && git log -1 --format="ch32fun commit %h %cd" )
ls -l /home/agents/dev/ch32fun/minichlink/minichlink
echo "== usb tree"
lsusb -t
echo "== uhubctl hubs (power switching capability)"
uhubctl 2>&1
echo "== groups"
id agents
echo "== end $(date)"
