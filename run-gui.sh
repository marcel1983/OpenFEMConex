#!/bin/sh
# Launches the interface from this checkout. Qt needs libxcb-cursor0; if it is not
# installed system-wide (sudo apt install libxcb-cursor0), a local copy is used when found.
here="$(cd "$(dirname "$0")" && pwd)"
local_libs="$HOME/.local/opt/openconex-libs/usr/lib/x86_64-linux-gnu"
[ -d "$local_libs" ] && export LD_LIBRARY_PATH="$local_libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$here/.venv/bin/python" -m openfemconex.gui.main "$@"
