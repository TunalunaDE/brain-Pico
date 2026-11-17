#!/bin/sh
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# adb_ui_dump.sh [ADB_SERIAL] - agent-hq: dump the clickable texts + bounds of the test tablet screen (uiautomator).
# usage: ui.sh  -> dumps clickable text/desc + bounds of the current screen
A="adb${1:+ -s $1}"   # ADB_SERIAL optional (only needed with more than one device)
$A shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1
$A shell cat /sdcard/ui.xml | tr '>' '\n' | grep -o '\(text\|content-desc\)="[^"]\+"[^/]*bounds="[^"]*"' | sed 's/ [a-z-]*="[^"]*"//g; s/" .*bounds=/" @/' | head -40
