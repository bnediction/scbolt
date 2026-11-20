#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"
project_dir="${tmpdir}/project"
annotations=()

trap 'rm -rf "${tmpdir}"' EXIT

for condition in ctrl treated integrated; do
    annotation="${project_dir}/omics/annot/${condition}/annot.h5ad"
    mkdir -p "$(dirname "${annotation}")"
    touch "${annotation}"
    annotations+=("${annotation}")
done

# Only dependency and parameter checks are exercised here. AnnData content and
# external runtimes have their own checks; the empty files mark trusted outputs.
run_check() {
    make -C "${repo_root}" check \
        PARAMS=tests/fixtures/params.mk \
        PROJECT_DIR="${project_dir}" \
        RESOURCES_DIR="${tmpdir}/resources" \
        SRA_CTRL= SRA_TREATED= LABEL= \
        __check_externals__=false \
        "$@"
}

if ! run_check TARGET=bn-submin OLD_FILES="${annotations[*]}" \
        > "${tmpdir}/trusted.out" 2>&1; then
    cat "${tmpdir}/trusted.out" >&2
    exit 1
fi
! grep -q 'required input route not defined' "${tmpdir}/trusted.out"
! grep -q 'required project parameter not defined: LABEL' "${tmpdir}/trusted.out"

if ! run_check TARGET=bin-cells OLD_FILES="${annotations[2]}" \
        > "${tmpdir}/integrated-only.out" 2>&1; then
    cat "${tmpdir}/integrated-only.out" >&2
    exit 1
fi

if ! run_check TARGET=bn-submin TRUST_EXISTING=true \
        > "${tmpdir}/trust-existing.out" 2>&1; then
    cat "${tmpdir}/trust-existing.out" >&2
    exit 1
fi

if run_check TARGET=bn-submin \
        OLD_FILES="${annotations[0]} ${annotations[2]}" \
        > "${tmpdir}/incomplete.out" 2>&1; then
    printf '%s\n' 'expected incomplete annotation trust to require an input route' >&2
    exit 1
fi
if ! grep -q 'required input route not defined' "${tmpdir}/incomplete.out"; then
    cat "${tmpdir}/incomplete.out" >&2
    exit 1
fi

if run_check TARGET=filtering OLD_FILES="${annotations[*]}" \
        > "${tmpdir}/filtering.out" 2>&1; then
    printf '%s\n' 'expected preprocessing without a source route to fail' >&2
    exit 1
fi
grep -q 'required input route not defined' "${tmpdir}/filtering.out"

if run_check TARGET=load-matrix OLD_FILES="${annotations[*]}" \
        > "${tmpdir}/load-matrix.out" 2>&1; then
    printf '%s\n' 'expected matrix download without a source route to fail' >&2
    exit 1
fi
grep -q 'required input route not defined' "${tmpdir}/load-matrix.out"

printf '%s\n' 'annotated entry tests passed'
