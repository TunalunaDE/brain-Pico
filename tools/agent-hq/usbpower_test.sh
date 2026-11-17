#!/bin/sh
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# usbpower_test.sh HUB PORT - cut one USB port for 3 s, show the port state before / off / on.
# Example: sh ~/usbpower_test.sh 4-1 3
H=$1; P=$2
echo "== before"; sudo uhubctl -l $H -p $P
sudo uhubctl -l $H -p $P -a off
sleep 3
echo "== after off"; sudo uhubctl -l $H -p $P
sudo uhubctl -l $H -p $P -a on
sleep 2
echo "== after on"; sudo uhubctl -l $H -p $P
