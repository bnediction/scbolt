#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

cellranger_dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __cellranger PARAMS=tests/fixtures/params.mk \
        MEMORY=512MiB ALIGNMENT_TOOL=cellranger
)"
grep -q -- '--localmem=1' <<< "${cellranger_dry_run}"
! grep -q -- '--localmem=512MiB' <<< "${cellranger_dry_run}"

cellranger_gib_dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __cellranger PARAMS=tests/fixtures/params.mk \
        MEMORY=2GiB ALIGNMENT_TOOL=cellranger
)"
grep -q -- '--localmem=3' <<< "${cellranger_gib_dry_run}"

velocyto_single_thread_dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __velocyto PARAMS=tests/fixtures/params.mk \
        MEMORY=50 JOBS=1 ALIGNMENT_TOOL=cellranger
)"
grep -q -- '--samtools-threads 1 --samtools-memory 50000' \
    <<< "${velocyto_single_thread_dry_run}"

velocyto_multithread_dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __velocyto PARAMS=tests/fixtures/params.mk \
        MEMORY=50 JOBS=16 ALIGNMENT_TOOL=cellranger
)"
grep -q -- '--samtools-threads 16 --samtools-memory 3125' \
    <<< "${velocyto_multithread_dry_run}"

velocyto_mib_dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __velocyto PARAMS=tests/fixtures/params.mk \
        MEMORY=512MiB JOBS=16 ALIGNMENT_TOOL=cellranger
)"
grep -q -- '--samtools-threads 16 --samtools-memory 33' \
    <<< "${velocyto_mib_dry_run}"

normalization_dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __normalization PARAMS=tests/fixtures/params.mk MEMORY=512MiB
)"
grep -q -- '--max-memory "512MiB"' <<< "${normalization_dry_run}"

dea_dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __dea PARAMS=tests/fixtures/params.mk MEMORY=512MiB
)"
grep -q -- '--max-memory "512MiB"' <<< "${dea_dry_run}"

make -C "${repo_root}" check TARGET=velocyto PARAMS=tests/fixtures/params.mk \
    __check_externals__=false MEMORY=512MiB JOBS=16 ALIGNMENT_TOOL=cellranger \
    > "${tmpdir}/memory-check.out"
grep -q 'core parameter valid: MEMORY=512MiB' "${tmpdir}/memory-check.out"

if make -C "${repo_root}" check TARGET=dea PARAMS=tests/fixtures/params.mk \
        __check_externals__=false MEMORY=abc > "${tmpdir}/memory-invalid.out" 2>&1; then
    printf '%s\n' "expected invalid MEMORY check to fail" >&2
    exit 1
fi
grep -q 'required positive memory size for core parameter MEMORY (current: abc)' \
    "${tmpdir}/memory-invalid.out"

config_output="$(
    make -C "${repo_root}" config PARAMS=tests/fixtures/params.mk MEMORY=512MiB
)"
grep -q 'Memory           : 512MiB' <<< "${config_output}"

config_gb_output="$(
    make -C "${repo_root}" config PARAMS=tests/fixtures/params.mk MEMORY=50
)"
grep -q 'Memory           : 50GB' <<< "${config_gb_output}"

raw_config_output="$(
    make -C "${repo_root}" config PARAMS=tests/fixtures/params.mk \
        MEMORY=512MiB CONFIG_RAW=true
)"
grep -q '^MEMORY=512MiB$' <<< "${raw_config_output}"
