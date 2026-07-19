#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

dry_run="$(
    make -C "${repo_root}" --always-make --dry-run \
        LOGGING=false \
        __max-nodes-lock \
        PARAMS=tests/fixtures/params.mk
)"

grep -Fq 'infer/spec/forbidden.txt' <<< "${dry_run}"
test "$(grep -c -- '--forbidden-nodes' <<< "${dry_run}")" -eq 2
grep -Eq -- \
    '--forbidden-nodes .*/infer/spec/forbidden\.txt' \
    <<< "${dry_run}"
grep -Eq -- \
    '--filter-grn .*/infer/genes/relaxed/comps\.txt' \
    <<< "${dry_run}"

spec_help="$(
    make -C "${repo_root}" module-help \
        TARGET=spec \
        PARAMS=tests/fixtures/params.mk \
        SCBOLT_CLI=true
)"

grep -Fq 'infer/spec/forbidden.txt' <<< "${spec_help}"
grep -Fq '  forbidden_nodes:' <<< "${spec_help}"

grep -Fq \
    'forbidden_nodes = set(read_specification_list("forbidden_nodes"))' \
    "${repo_root}/scripts/infer/spec.py"
grep -Fq \
    'with open(args.forbidden_nodes, "w") as file:' \
    "${repo_root}/scripts/infer/spec.py"
grep -Fq \
    'grn = remove_forbidden_nodes(grn, forbidden_nodes)' \
    "${repo_root}/scripts/infer/spec.py"
