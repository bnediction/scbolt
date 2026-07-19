#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

params="${tmpdir}/params.mk"
project="${tmpdir}/project"
submin="${project}/infer/bn/submin"
influence_graph="${submin}/influence_graph"

cat > "${params}" <<MK
PROJECT_DIR = ${project}
RESOURCES_DIR = ${tmpdir}/resources
ORGANISM = mouse
CONDITIONS = ctrl treated
SRA_CTRL = SRR000001
SRA_TREATED = SRR000002
LABEL = Prom Rep
SPEC_FILE = ${tmpdir}/spec.yml
PRIOR_KNOWLEDGE = dorothea
DOROTHEA_API = legacy
DOROTHEA_LEVELS = A
MACROSTATE_METHOD = knnsc
BIN_METHOD = consensus
INFER_LIMIT = 5
TIMEOUT_SEED = 1h
MK

touch "${tmpdir}/spec.yml"

assert_reset_build_target() {
    local module="$1"
    local expected_target="$2"
    local database="${tmpdir}/${module}.make-db"

    make -C "${repo_root}" -f Makefile -pn "__${module}" \
        PARAMS="${params}" LOGGING=false \
        "CLI_RESET_TARGETS+=${module}" > "${database}" 2>/dev/null
    grep -F ".PHONY:" "${database}" | grep -Fq "${expected_target}"
}

assert_reset_build_target \
    bn-submin \
    "${submin}/influence_graph/aggregate.pdf"
assert_reset_build_target \
    bn-diverse \
    "${project}/infer/bn/diverse/influence_graph/aggregate.pdf"

default_config="$("${repo_root}/bin/scbolt" config --default --raw)"
default_formats="$(
    awk -F= '$1 == "CONFIG_FORMATS" { print $2; exit }' <<< "${default_config}"
)"
test "${default_formats}" = "csv"

make_solution_dir() {
    local dir="$1"

    mkdir -p "${dir}"
    touch \
        "${dir}/model.bnet" \
        "${dir}/noi.txt" \
        "${dir}/configs.csv" \
        "${dir}/ig.dot"
}

mkdir -p "${submin}"
make_solution_dir "${submin}/1"
make_solution_dir "${submin}/2"
make_solution_dir "${submin}/3"

set +e
output="$(
    printf 'n\n' | make -C "${repo_root}" __check-bn-submin-outputs \
        PARAMS="${params}" LOGGING=false 2>&1
)"
status="$?"
set -e

printf '%s\n' "${output}"
test "${status}" -ne 0
grep -q "Detected incomplete outputs for target 'bn-submin'" <<< "${output}"
grep -q "infer/bn/submin/influence_graph/aggregate.pdf" <<< "${output}"
grep -q "infer/bn/submin/influence_graph/aggregate_with_isolates.pdf" <<< "${output}"
grep -q "infer/bn/submin/influence_graph/function_families.pdf" <<< "${output}"
grep -q "infer/bn/submin/influence_graph/feedback_core.pdf" <<< "${output}"
grep -q "infer/bn/submin/4/model.bnet" <<< "${output}"
grep -q "infer/bn/submin/4/configs.csv" <<< "${output}"
grep -q "more output(s)" <<< "${output}"
case "${output}" in
    *$'more output(s)\n\nRemove partial outputs and rerun inference?'*) ;;
    *)
        echo "missing blank line before incomplete-output prompt" >&2
        exit 1
        ;;
esac
! grep -q "infer/bn/submin/4/configs.cfg" <<< "${output}"
! grep -q "infer/bn/submin/4/ig.neato" <<< "${output}"
grep -q "Inference aborted." <<< "${output}"

mkdir -p "${influence_graph}"
touch \
    "${influence_graph}/aggregate.pdf" \
    "${influence_graph}/aggregate_with_isolates.pdf" \
    "${influence_graph}/function_families.pdf" \
    "${influence_graph}/feedback_core.pdf" \
    "${submin}/.scbolt.json"

make -C "${repo_root}" __check-bn-submin-outputs \
    PARAMS="${params}" LOGGING=false > "${tmpdir}/complete.out" 2>&1
! grep -q "infer/bn/submin/4/model.bnet" "${tmpdir}/complete.out"

spec_dir="${project}/infer/spec"
lock_dir="${project}/infer/genes/lock"
mkdir -p "${spec_dir}" "${lock_dir}"
touch \
    "${spec_dir}/model.bo" \
    "${spec_dir}/mstates.csv" \
    "${spec_dir}/important.txt" \
    "${spec_dir}/mandatory.txt" \
    "${spec_dir}/forbidden.txt" \
    "${lock_dir}/comps.txt" \
    "${influence_graph}/aggregate.pdf"

old_files=(
    "${spec_dir}/model.bo"
    "${spec_dir}/mstates.csv"
    "${spec_dir}/important.txt"
    "${spec_dir}/mandatory.txt"
    "${spec_dir}/forbidden.txt"
    "${lock_dir}/comps.txt"
)
old_file_args=()
for old_file in "${old_files[@]}"; do
    old_file_args+=("--old-file=${old_file}")
done

without_reset="$(
    make -C "${repo_root}" --dry-run __bn-submin \
        PARAMS="${params}" LOGGING=false \
        "${old_file_args[@]}" 2>&1
)"
with_reset="$(
    make -C "${repo_root}" --dry-run __bn-submin \
        PARAMS="${params}" LOGGING=false \
        CLI_RESET_TARGETS+=bn-submin \
        "${old_file_args[@]}" 2>&1
)"

! grep -q '"RULE" "bn-submin"' <<< "${without_reset}"
grep -q '"RULE" "bn-submin"' <<< "${with_reset}"

cli_with_reset="$(
    "${repo_root}/bin/scbolt" dry-run bn-submin \
        --params="${params}" \
        --reset-target=bn-submin 2>&1
)"
grep -q '"RULE" "bn-submin"' <<< "${cli_with_reset}"
grep -q 'infer.py submin' <<< "${cli_with_reset}"
