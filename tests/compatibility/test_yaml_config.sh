#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
scbolt="${repo_root}/bin/scbolt"
legacy="${repo_root}/tests/fixtures/params.mk"
yaml="${repo_root}/tests/fixtures/scbolt.yml"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

run_standalone_scbolt() (
    cd "${tmpdir}"
    "${scbolt}" "$@"
)

run_standalone_scbolt config --raw --params="${legacy}" \
    | sed '/^PARAMS=/d' > "${tmpdir}/legacy.config"
run_standalone_scbolt config --raw --config="${yaml}" \
    | sed '/^PARAMS=/d' > "${tmpdir}/yaml.config"
diff -u "${tmpdir}/legacy.config" "${tmpdir}/yaml.config"

cat > "${tmpdir}/config-python" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "-c" ]; then
    exit 0
fi
python3 "$@"
printf '\n'
EOF
chmod +x "${tmpdir}/config-python"
SCBOLT_CONFIG_PYTHON="${tmpdir}/config-python" \
    run_standalone_scbolt spec help --config="${yaml}" \
    > "${tmpdir}/blank-line-runner.out"
grep -Fq 'usage: scbolt spec' "${tmpdir}/blank-line-runner.out"

run_standalone_scbolt dry-run knnsc --params="${legacy}" \
    | sed -E 's#/tmp/scbolt-[A-Za-z0-9]+#/tmp/scbolt-TMP#g' \
    > "${tmpdir}/legacy.dry-run"
run_standalone_scbolt dry-run knnsc --config="${yaml}" \
    | sed -E 's#/tmp/scbolt-[A-Za-z0-9]+#/tmp/scbolt-TMP#g' \
    > "${tmpdir}/yaml.dry-run"
diff -u "${tmpdir}/legacy.dry-run" "${tmpdir}/yaml.dry-run"

run_standalone_scbolt config --raw --config="${yaml}" --neighbors=14 \
    > "${tmpdir}/override.config"
grep -qx 'NEIGHBORS=14' "${tmpdir}/override.config"

run_standalone_scbolt config --raw --config="${yaml}" --alignment-tool=cellranger \
    > "${tmpdir}/alignment-override.config"
grep -qx 'ALIGNMENT_TOOL=cellranger' "${tmpdir}/alignment-override.config"

run_standalone_scbolt config --raw --config="${yaml}" --omics-hvg-method=binning \
    --bin-hvg-method=loess > "${tmpdir}/hvg-override.config"
grep -qx 'OMICS_HVG_METHOD=binning' "${tmpdir}/hvg-override.config"
grep -qx 'BIN_HVG_METHOD=loess' "${tmpdir}/hvg-override.config"

make --no-print-directory -s PARAMS="${legacy}" \
    --eval='.PHONY: __test_clustering_metadata' \
    --eval='__test_clustering_metadata: ; @printf "%s\n" "$(call metadata_param_args,clustering)"' \
    __test_clustering_metadata > "${tmpdir}/clustering-metadata.args"
grep -Fq -- "--param 'OMICS_HVG_METHOD=loess'" \
    "${tmpdir}/clustering-metadata.args"
grep -Fq -- "--param 'OMICS_HVG_TOP='" \
    "${tmpdir}/clustering-metadata.args"
! grep -Fq 'ANALYSIS_HVG_' "${tmpdir}/clustering-metadata.args"

make --no-print-directory -s PARAMS="${legacy}" \
    --eval='.PHONY: __test_sensitive_parameters' \
    --eval='__test_sensitive_parameters: ; @$(foreach module,$(reset_stages),printf "%s\n" "$(strip $(sensitive_params_$(module)))";)' \
    __test_sensitive_parameters > "${tmpdir}/sensitive-parameters.txt"
python3 "${repo_root}/scripts/utils/project_config.py" export "${yaml}" \
    > "${tmpdir}/project-parameters.txt"
awk '
    NR == FNR {
        for (field = 1; field <= NF; field++) {
            sensitive[$field] = 1
        }
        next
    }
    /^SCBOLT_PUBLIC_PARAMETER_/ {
        mapped[substr($1, 25)] = 1
    }
    END {
        for (name in sensitive) {
            if (!(name in mapped)) {
                print "metadata parameter has no public mapping: " name > "/dev/stderr"
                missing = 1
            }
        }
        exit missing
    }
' "${tmpdir}/sensitive-parameters.txt" "${tmpdir}/project-parameters.txt"

cat > "${tmpdir}/count-files.yml" <<'EOF'
conditions: [ctrl, treated]
count-file:
  ctrl: ctrl-counts.h5ad
  treated: treated-counts.h5ad
EOF
run_standalone_scbolt config --raw --config="${tmpdir}/count-files.yml" \
    > "${tmpdir}/count-files.config"
grep -Fqx "COUNT_FILE_CTRL=${tmpdir}/ctrl-counts.h5ad" \
    "${tmpdir}/count-files.config"
grep -Fqx "COUNT_FILE_TREATED=${tmpdir}/treated-counts.h5ad" \
    "${tmpdir}/count-files.config"
touch "${tmpdir}/ctrl-counts.h5ad" "${tmpdir}/treated-counts.h5ad"
run_standalone_scbolt dry-run filtering --config="${tmpdir}/count-files.yml" \
    > "${tmpdir}/count-files.dry-run"
grep -Fq "filter.py ctrl-counts.h5ad" \
    "${tmpdir}/count-files.dry-run"
grep -Fq "filter.py treated-counts.h5ad" \
    "${tmpdir}/count-files.dry-run"

run_standalone_scbolt config --raw --config="${tmpdir}/count-files.yml" \
    --count-file-ctrl=override-counts.h5ad \
    > "${tmpdir}/count-files-override.config"
grep -Fqx "COUNT_FILE_CTRL=${tmpdir}/override-counts.h5ad" \
    "${tmpdir}/count-files-override.config"

cat > "${tmpdir}/macrostate-files.yml" <<'EOF'
conditions: [ctrl, treated]
macrostate-file-ctrl: ctrl-mstates.h5ad
macrostate-file-treated: treated-mstates.h5ad
EOF
run_standalone_scbolt config --raw --config="${tmpdir}/macrostate-files.yml" \
    > "${tmpdir}/macrostate-files.config"
grep -Fqx "MACROSTATE_FILE_CTRL=${tmpdir}/ctrl-mstates.h5ad" \
    "${tmpdir}/macrostate-files.config"
grep -Fqx "MACROSTATE_FILE_TREATED=${tmpdir}/treated-mstates.h5ad" \
    "${tmpdir}/macrostate-files.config"

cat > "${tmpdir}/shared-macrostate-file.yml" <<'EOF'
conditions: [ctrl, treated]
macrostate-file: all-mstates.h5ad
EOF
run_standalone_scbolt config --raw --config="${tmpdir}/shared-macrostate-file.yml" \
    > "${tmpdir}/shared-macrostate-file.config"
grep -Fqx "MACROSTATE_FILE=${tmpdir}/all-mstates.h5ad" \
    "${tmpdir}/shared-macrostate-file.config"

locator_project="${tmpdir}/locator-project"
mkdir -p "${locator_project}/config" "${locator_project}/work"
cat > "${locator_project}/.scbolt" <<'EOF'
CONFIG=config/scbolt.yml
EOF
cat > "${locator_project}/config/scbolt.yml" <<'EOF'
project-dir: project
resources-dir: resources
spec-file: config/spec.yml
old-files: [project/omics/annot/annot.h5ad]
count-file: data/counts.h5ad
EOF
(
    cd "${locator_project}/work"
    "${scbolt}" config --raw > "${tmpdir}/locator-project.config"
)
grep -Fqx "PROJECT_DIR=${locator_project}/project" \
    "${tmpdir}/locator-project.config"
grep -Fqx "RESOURCES_DIR=${locator_project}/resources" \
    "${tmpdir}/locator-project.config"
grep -Fqx "SPEC_FILE=${locator_project}/config/spec.yml" \
    "${tmpdir}/locator-project.config"
grep -Fqx "OLD_FILES=${locator_project}/project/omics/annot/annot.h5ad" \
    "${tmpdir}/locator-project.config"
grep -Fqx "COUNT_FILE=${locator_project}/data/counts.h5ad" \
    "${tmpdir}/locator-project.config"

printf '%s\n' "YAML configuration compatibility tests passed"
