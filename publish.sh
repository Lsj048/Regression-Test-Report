#!/bin/sh
# Calling this command means the report has been reviewed for public release.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$project_dir/scripts/publish_report.py" "$@"
