#!/bin/sh
set -eu
guarded_python="${IPHONE_USE_GUARDED_PYTHON:-$HOME/.local/share/iphone-use-guarded/venv/bin/python}"
if [ ! -x "$guarded_python" ]; then
    echo 'The guarded Python environment is not installed; do not fall back to raw input.' >&2
    exit 2
fi
exec "$guarded_python" "$(dirname "$0")/run-guarded.py" "$@"
