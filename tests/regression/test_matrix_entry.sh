#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __filtering PARAMS=tests/fixtures/params-matrix.mk
)"
grep -q 'download/load_geo.py' <<< "${dry_run}"
! grep -q 'parallel-fastq-dump' <<< "${dry_run}"
! grep -q 'velocyto run' <<< "${dry_run}"

conflict_params="${tmpdir}/conflict.mk"
cat > "${conflict_params}" <<'MK'
PROJECT_DIR = tests/output-matrix
RESOURCES_DIR = tests/resources
CONDITIONS = ctrl
ORGANISM = human
SRA_CTRL = SRR000001
GSM_CTRL = GSM5492245
MK

if make -C "${repo_root}" check TARGET=load-matrix PARAMS="${conflict_params}" \
        __check_externals__=false > "${tmpdir}/conflict.out" 2>&1; then
    printf '%s\n' "expected SRA/GSM conflict check to fail" >&2
    exit 1
fi
grep -q "variable conflict: input routes are mutually exclusive" \
    "${tmpdir}/conflict.out"
grep -q "specified: SRA_\\*, GSM_\\*" "${tmpdir}/conflict.out"

cat > "${conflict_params}" <<'MK'
PROJECT_DIR = tests/output-matrix
RESOURCES_DIR = tests/resources
CONDITIONS = ctrl
ORGANISM = human
GSM_CTRL = GSM5492245
COUNT_FILES = counts.h5ad
MK

if make -C "${repo_root}" check TARGET=load-matrix PARAMS="${conflict_params}" \
        __check_externals__=false > "${tmpdir}/conflict-count.out" 2>&1; then
    printf '%s\n' "expected GSM/COUNT_FILES conflict check to fail" >&2
    exit 1
fi
grep -q "specified: GSM_\\*, COUNT_FILES" "${tmpdir}/conflict-count.out"

if make -C "${repo_root}" check TARGET=velocity PARAMS=tests/fixtures/params-matrix.mk \
        __check_externals__=false > "${tmpdir}/velocity.out" 2>&1; then
    printf '%s\n' "expected matrix-mode velocity check to fail" >&2
    exit 1
fi
grep -q "matrix input mode does not provide spliced/unspliced layers" \
    "${tmpdir}/velocity.out"

help_output="$(
    make -C "${repo_root}" module-help TARGET=load-matrix \
        PARAMS=tests/fixtures/params-matrix.mk SCBOLT_CLI=true
)"
grep -q 'GSM_CTRL' <<< "${help_output}"

unnamed_params="${tmpdir}/unnamed.mk"
cat > "${unnamed_params}" <<'MK'
PROJECT_DIR = tests/output-unnamed
RESOURCES_DIR = tests/resources
CONDITIONS =
ORGANISM = human
GSM = GSM5492245
CC_CORRECTION = false
LABEL = Cluster
SPEC_FILE = spec.yml
MK

unnamed_dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __filtering PARAMS="${unnamed_params}"
)"
grep -q 'tests/output-unnamed/omics/count/counts.h5ad' <<< "${unnamed_dry_run}"
! grep -q 'tests/output-unnamed/unique/' <<< "${unnamed_dry_run}"
grep -q 'download/load_geo.py' <<< "${unnamed_dry_run}"

unnamed_help_output="$(
    make -C "${repo_root}" module-help TARGET=load-matrix \
        PARAMS="${unnamed_params}" SCBOLT_CLI=true
)"
grep -q '^  GSM' <<< "${unnamed_help_output}"
! grep -q 'GSM_UNIQUE' <<< "${unnamed_help_output}"

if ! make -C "${repo_root}" check TARGET=load-matrix PARAMS="${unnamed_params}" \
        __check_externals__=false > "${tmpdir}/unnamed-check.out" 2>&1; then
    cat "${tmpdir}/unnamed-check.out" >&2
    exit 1
fi
grep -q 'CONDITIONS=unnamed' "${tmpdir}/unnamed-check.out"
grep -q 'GSM=GSM5492245' "${tmpdir}/unnamed-check.out"

cat > "${unnamed_params}" <<'MK'
PROJECT_DIR = tests/output-unnamed
RESOURCES_DIR = tests/resources
CONDITIONS =
ORGANISM = human
SRA = SRR000001
GSM = GSM5492245
MK

if make -C "${repo_root}" check TARGET=load-matrix PARAMS="${unnamed_params}" \
        __check_externals__=false > "${tmpdir}/unnamed-conflict.out" 2>&1; then
    printf '%s\n' "expected unnamed SRA/GSM conflict check to fail" >&2
    exit 1
fi
grep -q "specified: SRA, GSM" "${tmpdir}/unnamed-conflict.out"

unnamed_sra_params="${tmpdir}/unnamed-sra.mk"
cat > "${unnamed_sra_params}" <<'MK'
PROJECT_DIR = tests/output-sra
RESOURCES_DIR = tests/resources
CONDITIONS =
ORGANISM = human
SRA = SRR000001 SRR000002
ALIGNMENT_TOOL = cellranger
LABEL = Cluster
SPEC_FILE = spec.yml
MK

unnamed_sra_dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __load-fastq PARAMS="${unnamed_sra_params}"
)"
grep -q 'for id in SRR000001 SRR000002' <<< "${unnamed_sra_dry_run}"
grep -q 'sample_naming="sample"' <<< "${unnamed_sra_dry_run}"
grep -q 'tests/output-sra/omics/fastq' <<< "${unnamed_sra_dry_run}"
! grep -q 'SRA_UNIQUE' <<< "${unnamed_sra_dry_run}"
! grep -q 'tests/output-sra/unique/' <<< "${unnamed_sra_dry_run}"

collision_params="${tmpdir}/collision.mk"
cat > "${collision_params}" <<'MK'
PROJECT_DIR = tests/output-collision
RESOURCES_DIR = tests/resources
CONDITIONS = bin infer
ORGANISM = human
GSM_BIN = GSM5492245
GSM_INFER = GSM5492245
CC_CORRECTION = false
LABEL = A B
SPEC_FILE = spec.yml
MACROSTATE_METHOD = knnsc
MK

collision_dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __clustering PARAMS="${collision_params}"
)"
grep -q 'tests/output-collision/omics/count/bin/counts.h5ad' <<< "${collision_dry_run}"
grep -q 'tests/output-collision/omics/clust/infer/clust.h5ad' <<< "${collision_dry_run}"
! grep -q 'tests/output-collision/bin/count' <<< "${collision_dry_run}"
! grep -q 'tests/output-collision/infer/clust' <<< "${collision_dry_run}"

collision_clustering_help="$(
    make -C "${repo_root}" module-help TARGET=clustering \
        PARAMS="${collision_params}" SCBOLT_CLI=true
)"
grep -q 'tests/output-collision/omics/clust/bin/clust.h5ad' \
    <<< "${collision_clustering_help}"
grep -q 'tests/output-collision/omics/clust/infer/clust.h5ad' \
    <<< "${collision_clustering_help}"

collision_annotation_help="$(
    make -C "${repo_root}" module-help TARGET=annotation \
        PARAMS="${collision_params}" SCBOLT_CLI=true
)"
grep -q 'tests/output-collision/omics/annot/bin/annot.h5ad' \
    <<< "${collision_annotation_help}"
grep -q 'tests/output-collision/omics/annot/infer/annot.h5ad' \
    <<< "${collision_annotation_help}"

collision_consensus_help="$(
    make -C "${repo_root}" module-help TARGET=bin-consensus \
        PARAMS="${collision_params}" SCBOLT_CLI=true
)"
grep -q 'tests/output-collision/bin/consensus/knnsc/mstates_bin.csv' \
    <<< "${collision_consensus_help}"

collision_bin_mstates_help="$(
    make -C "${repo_root}" module-help TARGET=bin-macrostates \
        PARAMS="${collision_params}" SCBOLT_CLI=true
)"
grep -q 'tests/output-collision/omics/mstates/knnsc/bin/mstates.csv' \
    <<< "${collision_bin_mstates_help}"
grep -q 'tests/output-collision/bin/scboolseq/macro/knnsc/mstates_bin.csv' \
    <<< "${collision_bin_mstates_help}"

collision_spec_help="$(
    make -C "${repo_root}" module-help TARGET=spec \
        PARAMS="${collision_params}" SCBOLT_CLI=true
)"
grep -q 'tests/output-collision/bin/consensus/knnsc/mstates_bin.csv' \
    <<< "${collision_spec_help}"
grep -q 'tests/output-collision/infer/spec/model.bo' \
    <<< "${collision_spec_help}"

custom_inference_help="$(
    make -C "${repo_root}" module-help TARGET=spec \
        PARAMS="${collision_params}" INFERENCE_DIR=infer-alternative \
        SCBOLT_CLI=true
)"
grep -q 'tests/output-collision/infer-alternative/spec/model.bo' \
    <<< "${custom_inference_help}"
! grep -q 'tests/output-collision/infer/spec/model.bo' \
    <<< "${custom_inference_help}"

if make -C "${repo_root}" --dry-run spec PARAMS="${collision_params}" \
        INFERENCE_DIR=../outside > "${tmpdir}/invalid-inference-dir.out" 2>&1; then
    printf '%s\n' "expected parent inference directory to fail" >&2
    exit 1
fi
grep -q 'INFERENCE_DIR must be a relative subdirectory of PROJECT_DIR' \
    "${tmpdir}/invalid-inference-dir.out"

if ! make -C "${repo_root}" check TARGET=load-fastq PARAMS="${unnamed_sra_params}" \
        __check_externals__=false > "${tmpdir}/unnamed-sra-check.out" 2>&1; then
    cat "${tmpdir}/unnamed-sra-check.out" >&2
    exit 1
fi
grep -q 'SRA=SRR000001 SRR000002' \
    "${tmpdir}/unnamed-sra-check.out"

no_entry_params="${tmpdir}/no-entry.mk"
cat > "${no_entry_params}" <<'MK'
CONDITIONS =
ORGANISM =
MK

if ! make -C "${repo_root}" config PARAMS="${no_entry_params}" \
        > "${tmpdir}/no-entry-config.out" 2>&1; then
    cat "${tmpdir}/no-entry-config.out" >&2
    exit 1
fi
grep -q '^- load-genome$' "${tmpdir}/no-entry-config.out"
grep -q '^- load-matrix$' "${tmpdir}/no-entry-config.out"
grep -q '^- scoring$' "${tmpdir}/no-entry-config.out"
grep -q '^- goea$' "${tmpdir}/no-entry-config.out"
grep -q '^- bn-diverse$' "${tmpdir}/no-entry-config.out"

printf '%s\n' "matrix entry tests passed"
