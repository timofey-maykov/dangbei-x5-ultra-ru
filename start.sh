#!/usr/bin/env bash
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$task_dir"
if [[ -f "$task_dir/dangbei-setup" ]]; then
    exec "$task_dir/dangbei-setup" "$@"
fi
# Source checkout only. Published archives include the standalone executable.
exec python3 install.py "$@"
