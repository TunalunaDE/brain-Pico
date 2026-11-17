#!/bin/sh
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# lib_push.sh [LIB_PARENT] - after lib_reset.py: put every .mpy of the pinned library (default: this repo's
# software/, which holds lib/) onto the Pico's empty /lib, then prove the imports (lib_import_check.py).
T=$(cd "$(dirname "$0")/.." && pwd)            # brain-Pico/tools
SRC=${1:-$T/../software}
cd "$SRC" || exit 1
for p in $(find lib -name '*.mpy' | sort); do
  python3 "$T/pico.py" put "$p" "/$p" 2>&1 | grep -E 'wrote|rror'
done
python3 "$T/pico.py" run "$T/restore/lib_import_check.py" 2>&1 | tail -n 2