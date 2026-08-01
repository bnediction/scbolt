#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"
project_dir="${tmpdir}/project"
spec_model="${project_dir}/infer/spec/model.bo"
soft_solution="${project_dir}/infer/genes/soft/comps.txt"
clustering_output="${project_dir}/omics/clust/integrated/clust.h5ad"

trap 'rm -rf "${tmpdir}"' EXIT

mkdir -p "$(dirname "${spec_model}")"
touch "${spec_model}"

run_helper() {
    local outfile="$1"
    shift

    make -s -C "${repo_root}" -f - \
        diagnostic_mode=true \
        PARAMS="tests/fixtures/params.mk" \
        PROJECT_DIR="${project_dir}" \
        "$@" inspect > "${outfile}" <<'MAKE'
scbolt_root := $(CURDIR)
makefile_path := $(scbolt_root)/Makefile

include $(scbolt_root)/make/config.mk
include $(scbolt_root)/make/modules.mk

.PHONY: inspect
inspect:
	@printf '%s\n' \
		'existing=$(strip $(existing_scbolt_targets))' \
		'rebuilding=$(strip $(reset_rebuild_modules))' \
		'auto=$(strip $(trust_existing_targets))' \
		'targets=$(strip $(trusted_make_targets))' \
		'old=$(strip $(trusted_old_files))' \
		'missing=$(strip $(missing_old_files))' \
		'options=$(strip $(trust_make_options))'
MAKE
}

run_helper "${tmpdir}/disabled.out"
grep -qx "existing=${spec_model}" "${tmpdir}/disabled.out"
grep -qx 'auto=' "${tmpdir}/disabled.out"
grep -qx 'targets=' "${tmpdir}/disabled.out"
grep -qx 'options=' "${tmpdir}/disabled.out"

run_helper "${tmpdir}/enabled.out" TRUST_EXISTING=true
grep -qx "existing=${spec_model}" "${tmpdir}/enabled.out"
grep -qx "auto=${spec_model}" "${tmpdir}/enabled.out"
grep -qx "targets=${spec_model}" "${tmpdir}/enabled.out"
grep -qx "options=--old-file=\"${spec_model}\"" "${tmpdir}/enabled.out"

mkdir -p "$(dirname "${soft_solution}")" "$(dirname "${clustering_output}")"
touch "${soft_solution}" "${clustering_output}"

run_helper "${tmpdir}/reset.out" \
    TRUST_EXISTING=true \
    TRUST_TARGET=spec \
    OLD_FILES="${spec_model}" \
    RESET_TARGET=spec
grep -q '^rebuilding=.*spec .*max-nodes-soft .*bn-submin' "${tmpdir}/reset.out"
grep -qx "auto=${clustering_output}" "${tmpdir}/reset.out"
grep -qx "targets=${clustering_output}" "${tmpdir}/reset.out"
grep -qx 'old=' "${tmpdir}/reset.out"
grep -qx 'missing=' "${tmpdir}/reset.out"
grep -qx "options=--old-file=\"${clustering_output}\"" "${tmpdir}/reset.out"

rm -f "${spec_model}"
run_helper "${tmpdir}/reset-missing-old.out" \
    OLD_FILES="${spec_model}" \
    RESET_TARGET=spec
grep -qx 'old=' "${tmpdir}/reset-missing-old.out"
grep -qx 'missing=' "${tmpdir}/reset-missing-old.out"
grep -qx 'options=' "${tmpdir}/reset-missing-old.out"

if make -s -C "${repo_root}" --dry-run filtering \
    PARAMS="tests/fixtures/params.mk" \
    TRUST_EXISTING=invalid \
    > "${tmpdir}/invalid.out" \
    2> "${tmpdir}/invalid.err"; then
    printf '%s\n' "expected invalid TRUST_EXISTING to fail" >&2
    exit 1
fi
grep -q \
    'unsupported value for parameter TRUST_EXISTING' \
    "${tmpdir}/invalid.err"

cli_help="$(
    "${repo_root}/bin/scbolt" help \
        --params="${repo_root}/tests/fixtures/params.mk"
)"
cli_trust_line="$(grep -n '^  --trust-target=<module\.\.\.>' <<< "${cli_help}" | cut -d: -f1)"
cli_existing_line="$(grep -n '^  --trust-existing ' <<< "${cli_help}" | cut -d: -f1)"
test "${cli_existing_line}" -eq "$((cli_trust_line + 1))"

make_help="$(
    make -s -C "${repo_root}" help \
        PARAMS="tests/fixtures/params.mk"
)"
make_trust_line="$(grep -n '^  TRUST_TARGET=<module\.\.\.>' <<< "${make_help}" | cut -d: -f1)"
make_existing_line="$(grep -n '^  TRUST_EXISTING=<bool>' <<< "${make_help}" | cut -d: -f1)"
test "${make_existing_line}" -eq "$((make_trust_line + 1))"
