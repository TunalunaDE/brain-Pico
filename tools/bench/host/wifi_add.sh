#!/bin/bash
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# Add a NEW WiFi network to this Pi (NetworkManager). Existing profiles are not touched.
# Asks for the Pi password once (sudo), the WiFi name, then the WiFi password (hidden).
sudo -v || exit 1
echo
echo "WiFi networks in range:"
sudo nmcli -f SSID,SIGNAL,SECURITY dev wifi list --rescan yes
echo
read -r -p "WiFi name (SSID, exactly as shown): " ssid
[ -n "$ssid" ] || { echo "no name given"; exit 1; }
sudo nmcli --ask dev wifi connect "$ssid" ifname wlan0
echo
echo "--- result ---"
nmcli -t -f DEVICE,STATE,CONNECTION dev | grep -E '^(eth0|wlan0)'
ip -4 -brief addr show eth0 wlan0
