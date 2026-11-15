#!/bin/bash
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$task_dir" || exit 1
exec /bin/bash "$task_dir/start.sh" "$@"
