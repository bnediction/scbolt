#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
make_database="$(
    make -f "${repo_root}/Makefile" -pn \
        PARAMS="${repo_root}/tests/fixtures/params.mk" 2>/dev/null
)"
precious_targets="$(printf '%s\n' "${make_database}" | grep '^\.PRECIOUS:')"

for output in \
    genes/soft/comps.txt \
    genes/consts/comps.txt \
    genes/relaxed/comps.txt \
    genes/seed/comps.txt \
    genes/lock/comps.txt; do
    if [[ " ${precious_targets} " != *"/infer/${output} "* ]]; then
        printf 'gene-selection partial output is not precious: %s\n' \
            "${output}" >&2
        exit 1
    fi
done
