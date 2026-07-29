#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"
child_pid=""

cleanup() {
    if [ -n "${child_pid}" ] && kill -0 "${child_pid}" 2>/dev/null; then
        kill -KILL "${child_pid}" 2>/dev/null || true
    fi
    for file in child.pid solution.txt timeout.status; do
        if [ -f "${tmpdir}/${file}" ]; then
            unlink "${tmpdir}/${file}"
        fi
    done
    rmdir "${tmpdir}"
}

trap cleanup EXIT

printf '%s\n' solution > "${tmpdir}/solution.txt"
metadata_timeout="$(
    make -f "${repo_root}/Makefile" --no-print-directory \
        PARAMS="${repo_root}/tests/fixtures/params.mk" \
        TEST_SOLUTION="${tmpdir}/solution.txt" \
        TIMEOUT_SOFT=5h \
        --eval='override write_scbolt_metadata = echo "$(3)"' \
        --eval='override print_warning = :' \
        --eval='.PHONY: __test_timeout_metadata' \
        --eval='__test_timeout_metadata: ; @exit_status=124; $(call check_inference_status,5h,max-nodes-soft,TIMEOUT_SOFT,,,${TEST_SOLUTION})' \
        __test_timeout_metadata
)"
test "${metadata_timeout}" = 'TIMEOUT_SOFT=5h'

metadata_capacity="$(
    make -f "${repo_root}/Makefile" --no-print-directory \
        PARAMS="${repo_root}/tests/fixtures/params.mk" \
        TEST_SOLUTION="${tmpdir}/solution.txt" \
        --eval='override write_scbolt_metadata = echo "$(4)"' \
        --eval='override print_warning = :' \
        --eval='.PHONY: __test_capacity_metadata' \
        --eval='__test_capacity_metadata: ; @exit_status=125; $(call check_inference_status,,max-nodes-soft,,,,${TEST_SOLUTION})' \
        __test_capacity_metadata
)"
grep -Fq -- '--solution-status partial' <<< "${metadata_capacity}"

set +e
metadata_interrupt="$(
    make -f "${repo_root}/Makefile" --no-print-directory \
        PARAMS="${repo_root}/tests/fixtures/params.mk" \
        TEST_SOLUTION="${tmpdir}/solution.txt" \
        TIMEOUT_SOFT=5h \
        --eval='override write_scbolt_metadata = echo "$(3)"' \
        --eval='override print_warning = :' \
        --eval='.PHONY: __test_interrupt_metadata' \
        --eval='__test_interrupt_metadata: ; @effective_inference_timeout() { echo 17s; }; exit_status=130; $(call check_inference_status,5h,max-nodes-soft,TIMEOUT_SOFT,,,${TEST_SOLUTION})' \
        __test_interrupt_metadata 2>/dev/null
)"
interrupt_status="$?"
set -e

test "${interrupt_status}" -ne 0
test "${metadata_interrupt}" = 'TIMEOUT_SOFT=17s'
unlink "${tmpdir}/solution.txt"

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
