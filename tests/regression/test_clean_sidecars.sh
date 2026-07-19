#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

project="${tmpdir}/project"
spec_dir="${project}/infer/spec"
params="${tmpdir}/params.mk"

printf '%s\n' \
    "PROJECT_DIR = ${project}" \
    "RESOURCES_DIR = ${tmpdir}/resources" \
    "ORGANISM = mouse" \
    "CONDITIONS =" \
    "GSM = GSM000001" \
    "LABEL = Prom Rep" \
    "SPEC_FILE = ${tmpdir}/spec.yml" \
    "PRIOR_KNOWLEDGE = dorothea" \
    "DOROTHEA_API = legacy" \
    "DOROTHEA_LEVELS = A" \
    "MACROSTATE_METHOD = knnsc" \
    "BIN_METHOD = consensus" \
    > "${params}"

mkdir -p "${spec_dir}"
touch "${tmpdir}/spec.yml"

outputs=(
    "${spec_dir}/model.bo"
    "${spec_dir}/mstates.csv"
    "${spec_dir}/important.txt"
    "${spec_dir}/mandatory.txt"
    "${spec_dir}/forbidden.txt"
)
sidecars=(
    "${spec_dir}/model.scbolt.json"
    "${spec_dir}/mstates.scbolt.json"
    "${spec_dir}/important.scbolt.json"
    "${spec_dir}/mandatory.scbolt.json"
    "${spec_dir}/forbidden.scbolt.json"
)

touch "${outputs[@]}" "${sidecars[@]}" "${spec_dir}/unrelated.scbolt.json"

(
    cd "${tmpdir}"
    make -f "${repo_root}/Makefile" clean \
        CLEAN_TARGET=spec \
        PARAMS="${params}" \
        LOGGING=false \
        > "${tmpdir}/clean.out"
)

for path in "${outputs[@]}" "${sidecars[@]}"; do
    if [ -e "${path}" ]; then
        printf 'expected clean to remove %s\n' "${path}" >&2
        exit 1
    fi
done

test -e "${spec_dir}/unrelated.scbolt.json"
grep -q "cleaned module 'spec'" "${tmpdir}/clean.out"
