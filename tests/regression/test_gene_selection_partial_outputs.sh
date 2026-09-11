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
    genes/soft/witness.lp \
    genes/consts/comps.txt \
    genes/consts/witness.lp \
    genes/relaxed/comps.txt \
    genes/relaxed/witness.lp \
    genes/seed/comps.txt \
    genes/seed/witness.lp \
    genes/lock/comps.txt \
    genes/lock/witness.lp; do
    if [[ " ${precious_targets} " != *"/infer/${output} "* ]]; then
        printf 'gene-selection partial output is not precious: %s\n' \
            "${output}" >&2
        exit 1
    fi
done
