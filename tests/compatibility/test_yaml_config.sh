#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
scbolt="${repo_root}/bin/scbolt"
legacy="${repo_root}/tests/fixtures/params.mk"
yaml="${repo_root}/tests/fixtures/scbolt.yml"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

"${scbolt}" config --raw --params="${legacy}" \
    | sed '/^PARAMS=/d' > "${tmpdir}/legacy.config"
"${scbolt}" config --raw --config="${yaml}" \
    | sed '/^PARAMS=/d' > "${tmpdir}/yaml.config"
diff -u "${tmpdir}/legacy.config" "${tmpdir}/yaml.config"

"${scbolt}" dry-run knnsc --params="${legacy}" \
    | sed -E 's#/tmp/scbolt-[A-Za-z0-9]+#/tmp/scbolt-TMP#g' \
    > "${tmpdir}/legacy.dry-run"
"${scbolt}" dry-run knnsc --config="${yaml}" \
    | sed -E 's#/tmp/scbolt-[A-Za-z0-9]+#/tmp/scbolt-TMP#g' \
    > "${tmpdir}/yaml.dry-run"
diff -u "${tmpdir}/legacy.dry-run" "${tmpdir}/yaml.dry-run"

"${scbolt}" config --raw --config="${yaml}" --neighbors=14 \
    > "${tmpdir}/override.config"
grep -qx 'NEIGHBORS=14' "${tmpdir}/override.config"

"${scbolt}" config --raw --config="${yaml}" --alignment-tool=cellranger \
    > "${tmpdir}/alignment-override.config"
grep -qx 'ALIGNMENT_TOOL=cellranger' "${tmpdir}/alignment-override.config"

"${scbolt}" config --raw --config="${yaml}" --omics-hvg-method=binning \
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
"${scbolt}" config --raw --config="${tmpdir}/count-files.yml" \
    > "${tmpdir}/count-files.config"
grep -Fqx "COUNT_FILE_CTRL=${tmpdir}/ctrl-counts.h5ad" \
    "${tmpdir}/count-files.config"
grep -Fqx "COUNT_FILE_TREATED=${tmpdir}/treated-counts.h5ad" \
    "${tmpdir}/count-files.config"
touch "${tmpdir}/ctrl-counts.h5ad" "${tmpdir}/treated-counts.h5ad"
"${scbolt}" dry-run filtering --config="${tmpdir}/count-files.yml" \
    > "${tmpdir}/count-files.dry-run"
grep -Fq "filter.py ${tmpdir}/ctrl-counts.h5ad" \
    "${tmpdir}/count-files.dry-run"
grep -Fq "filter.py ${tmpdir}/treated-counts.h5ad" \
    "${tmpdir}/count-files.dry-run"

"${scbolt}" config --raw --config="${tmpdir}/count-files.yml" \
    --count-file-ctrl=override-counts.h5ad \
    > "${tmpdir}/count-files-override.config"
grep -Fqx "COUNT_FILE_CTRL=${repo_root}/override-counts.h5ad" \
    "${tmpdir}/count-files-override.config"

cat > "${tmpdir}/macrostate-files.yml" <<'EOF'
conditions: [ctrl, treated]
macrostate-file-ctrl: ctrl-mstates.h5ad
macrostate-file-treated: treated-mstates.h5ad
EOF
"${scbolt}" config --raw --config="${tmpdir}/macrostate-files.yml" \
    > "${tmpdir}/macrostate-files.config"
grep -Fqx "MACROSTATE_FILE_CTRL=${tmpdir}/ctrl-mstates.h5ad" \
    "${tmpdir}/macrostate-files.config"
grep -Fqx "MACROSTATE_FILE_TREATED=${tmpdir}/treated-mstates.h5ad" \
    "${tmpdir}/macrostate-files.config"

cat > "${tmpdir}/shared-macrostate-file.yml" <<'EOF'
conditions: [ctrl, treated]
macrostate-file: all-mstates.h5ad
EOF
"${scbolt}" config --raw --config="${tmpdir}/shared-macrostate-file.yml" \
    > "${tmpdir}/shared-macrostate-file.config"
grep -Fqx "MACROSTATE_FILE=${tmpdir}/all-mstates.h5ad" \
    "${tmpdir}/shared-macrostate-file.config"

printf '%s\n' "YAML configuration compatibility tests passed"
