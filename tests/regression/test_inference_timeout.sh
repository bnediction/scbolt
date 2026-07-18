#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"
child_pid=""

cleanup() {
    if [ -n "${child_pid}" ] && kill -0 "${child_pid}" 2>/dev/null; then
        kill -KILL "${child_pid}" 2>/dev/null || true
    fi
    for file in child.pid timeout.status; do
        if [ -f "${tmpdir}/${file}" ]; then
            unlink "${tmpdir}/${file}"
        fi
    done
    rmdir "${tmpdir}"
}

trap cleanup EXIT

set +e
"${repo_root}/bin/scbolt-timeout" \
    "${tmpdir}/timeout.status" \
    1s \
    python -c '
import os
import pathlib
import time

pathlib.Path("'"${tmpdir}/child.pid"'").write_text(str(os.getpid()))
time.sleep(60)
'
status="$?"
set -e

test "${status}" -eq 0
grep -qx '124' "${tmpdir}/timeout.status"
child_pid="$(cat "${tmpdir}/child.pid")"

for _ in {1..20}; do
    if ! kill -0 "${child_pid}" 2>/dev/null; then
        child_pid=""
        exit 0
    fi
    sleep 0.1
done

printf 'timed-out child process is still running: %s\n' "${child_pid}" >&2
exit 1
