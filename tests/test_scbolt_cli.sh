#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scbolt="${repo_root}/bin/scbolt"
makefile="${repo_root}/Makefile"
tmpdir="$(mktemp -d)"
record="${tmpdir}/make.args"

trap 'rm -rf "${tmpdir}"' EXIT

fakebin="${tmpdir}/bin"
mkdir -p "${fakebin}"
ln -s "${scbolt}" "${fakebin}/scbolt"

cat > "${fakebin}/make" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" > "${SCBOLT_TEST_RECORD}"
EOF
chmod +x "${fakebin}/make"

run_scbolt() {
    local project_dir="$1"
    shift

    rm -f "${record}"
    (
        cd "${project_dir}"
        PATH="${fakebin}:${PATH}" SCBOLT_TEST_RECORD="${record}" "${scbolt}" "$@"
    )
}

run_scbolt_from_path() {
    local project_dir="$1"
    shift

    rm -f "${record}"
    (
        cd "${project_dir}"
        PATH="${fakebin}:${PATH}" SCBOLT_TEST_RECORD="${record}" scbolt "$@"
    )
}

expect_make_args() {
    local expected="${tmpdir}/expected.args"

    printf '%s\n' "$@" > "${expected}"
    diff -u "${expected}" "${record}"
}

project="${tmpdir}/project"
mkdir -p "${project}"
printf '# test params\n' > "${project}/params.mk"

for help_arg in "" help -h --help; do
    if [ -z "${help_arg}" ]; then
        run_scbolt "${project}"
    else
        run_scbolt "${project}" "${help_arg}"
    fi
    expect_make_args -f "${makefile}" help SCBOLT_CLI=true
done

run_scbolt_from_path "${project}" help
expect_make_args -f "${makefile}" help SCBOLT_CLI=true

run_scbolt "${project}" show-config help
expect_make_args -f "${makefile}" show-config HELP=true SCBOLT_CLI=true

run_scbolt "${project}" show-config -h
expect_make_args -f "${makefile}" show-config HELP=true SCBOLT_CLI=true

run_scbolt "${project}" show-config --help
expect_make_args -f "${makefile}" show-config HELP=true SCBOLT_CLI=true

run_scbolt "${project}" check --help
expect_make_args -f "${makefile}" check HELP=true SCBOLT_CLI=true

run_scbolt "${project}" dry-run help
expect_make_args -f "${makefile}" dry-run HELP=true SCBOLT_CLI=true

run_scbolt "${project}" annotation help --params=params.mk
expect_make_args \
    -f "${makefile}" \
    module-help \
    TARGET=annotation \
    SCBOLT_CLI=true \
    PARAMS=params.mk

run_scbolt "${project}" annotation --help --params=params.mk
expect_make_args \
    -f "${makefile}" \
    module-help \
    TARGET=annotation \
    SCBOLT_CLI=true \
    PARAMS=params.mk

run_scbolt "${project}" bn-submin -h --params=params.mk
expect_make_args \
    -f "${makefile}" \
    module-help \
    TARGET=bn-submin \
    SCBOLT_CLI=true \
    PARAMS=params.mk

run_scbolt "${project}" progress --help
expect_make_args -f "${makefile}" progress HELP=true SCBOLT_CLI=true

run_scbolt "${project}" clean help
expect_make_args -f "${makefile}" clean HELP=true SCBOLT_CLI=true

(
    cd "${project}"
    "${scbolt}" init --help > "${tmpdir}/init-help.out"
)
grep -qx 'usage: scbolt init \[<params.mk>\] \[options\]' "${tmpdir}/init-help.out"
grep -q '^Parameters$' "${tmpdir}/init-help.out"
grep -q '^  --remove' "${tmpdir}/init-help.out"
grep -q '^  --show' "${tmpdir}/init-help.out"

(
    cd "${project}"
    "${scbolt}" init params.mk > "${tmpdir}/init.out" 2> "${tmpdir}/init.err"
)
grep -qx 'PARAMS=params.mk' "${project}/.scbolt"
grep -q 'Parameter file: params.mk' "${tmpdir}/init.out"
grep -qx '✓ scBOLT project initialized.' "${tmpdir}/init.out"

printf '# paper params\n' > "${project}/paper.mk"
(
    cd "${project}"
    "${scbolt}" init paper.mk > "${tmpdir}/reinit.out" 2> "${tmpdir}/reinit.err"
)
grep -qx 'PARAMS=paper.mk' "${project}/.scbolt"
grep -q '^Parameter file: params.mk -> paper.mk$' "${tmpdir}/reinit.out"
grep -qx '✓ scBOLT project updated.' "${tmpdir}/reinit.out"

printf '# spaced params\n' > "${project}/spaced.mk"
(
    cd "${project}"
    printf 'spaced.mk \n' | "${scbolt}" init \
        > "${tmpdir}/spaced-init.out" \
        2> "${tmpdir}/spaced-init.err"
)
grep -qx 'PARAMS=spaced.mk' "${project}/.scbolt"
grep -q '^Parameter file: paper.mk -> spaced.mk$' "${tmpdir}/spaced-init.out"
grep -qx '✓ scBOLT project updated.' "${tmpdir}/spaced-init.out"

(
    cd "${project}"
    "${scbolt}" init spaced.mk > "${tmpdir}/unchanged-init.out"
)
grep -qx 'PARAMS=spaced.mk' "${project}/.scbolt"
grep -q '^Parameter file: spaced.mk$' "${tmpdir}/unchanged-init.out"
grep -qx '⚠ scBOLT project unchanged.' "${tmpdir}/unchanged-init.out"

mkdir -p "${project}/nested/path"
(
    cd "${project}/nested/path"
    "${scbolt}" init --show > "${tmpdir}/show-init.out"
)
grep -qx "Parameter file: ${project}/spaced.mk" "${tmpdir}/show-init.out"

(
    cd "${project}/nested/path"
    "${scbolt}" init --remove > "${tmpdir}/remove-init.out"
)
test ! -e "${project}/.scbolt"
grep -qx "Project file: ${project}/.scbolt" "${tmpdir}/remove-init.out"
grep -qx 'Parameter file: spaced.mk' "${tmpdir}/remove-init.out"
grep -qx '✓ scBOLT project configuration removed.' "${tmpdir}/remove-init.out"

(
    cd "${project}"
    "${scbolt}" init spaced.mk > "${tmpdir}/restore-init.out"
)
grep -qx 'PARAMS=spaced.mk' "${project}/.scbolt"

if (
    cd "${project}"
    "${scbolt}" init --remove spaced.mk > "${tmpdir}/bad-remove-init.out" \
        2> "${tmpdir}/bad-remove-init.err"
); then
    printf '%s\n' "expected init --remove with params file to fail" >&2
    exit 1
fi
grep -qx "✗ Use either '--remove' or a parameter file, not both." \
    "${tmpdir}/bad-remove-init.err"

if (
    cd "${project}"
    "${scbolt}" init --show spaced.mk > "${tmpdir}/bad-show-init.out" \
        2> "${tmpdir}/bad-show-init.err"
); then
    printf '%s\n' "expected init --show with params file to fail" >&2
    exit 1
fi
grep -qx "✗ Use either '--show' or a parameter file, not both." \
    "${tmpdir}/bad-show-init.err"

no_project="${tmpdir}/no-project"
mkdir -p "${no_project}"
(
    cd "${no_project}"
    "${scbolt}" init --remove > "${tmpdir}/missing-remove-init.out"
)
grep -qx 'Project file not found.' "${tmpdir}/missing-remove-init.out"
grep -qx '⚠ scBOLT project unchanged.' "${tmpdir}/missing-remove-init.out"

if (
    cd "${no_project}"
    "${scbolt}" init --show > "${tmpdir}/missing-show-init.out" \
        2> "${tmpdir}/missing-show-init.err"
); then
    printf '%s\n' "expected init --show without params to fail" >&2
    exit 1
fi
grep -qx '✗ No parameter file found.' "${tmpdir}/missing-show-init.err"

run_scbolt "${project}" bn-submin
expect_make_args -f "${makefile}" bn-submin "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" clean
expect_make_args -f "${makefile}" clean "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" clean --all --params=params.mk
expect_make_args -f "${makefile}" clean CLEAN_TARGET=all PARAMS=params.mk

if run_scbolt "${project}" clean --all macrostates > "${tmpdir}/bad-clean.out" \
    2> "${tmpdir}/bad-clean.err"; then
    printf '%s\n' "expected clean --all with explicit modules to fail" >&2
    exit 1
fi
grep -qx "✗ Use either '--all' or explicit modules, not both." "${tmpdir}/bad-clean.err"

run_scbolt "${project}" clean macrostates bn-submin --params=params.mk
expect_make_args \
    -f "${makefile}" \
    clean \
    "CLEAN_TARGET=macrostates bn-submin" \
    PARAMS=params.mk

printf '# override params\n' > "${project}/override.mk"
printf '# wrong params\n' > "${project}/spec.yml"
if (
    cd "${project}"
    "${scbolt}" init spec.yml > "${tmpdir}/bad-init.out" 2> "${tmpdir}/bad-init.err"
); then
    printf '%s\n' "expected init with non-.mk file to fail" >&2
    exit 1
fi
grep -qx 'Parameter file must have a .mk extension: spec.yml' "${tmpdir}/bad-init.err"
grep -qx '✗ scBOLT project update failed.' "${tmpdir}/bad-init.err"

if (
    cd "${project}"
    "${scbolt}" init us > "${tmpdir}/missing-init.out" 2> "${tmpdir}/missing-init.err"
); then
    printf '%s\n' "expected init with missing file to fail" >&2
    exit 1
fi
grep -qx 'Parameter file not found: us' "${tmpdir}/missing-init.err"
grep -qx '✗ scBOLT project update failed.' "${tmpdir}/missing-init.err"

fresh_project="${tmpdir}/fresh-project"
mkdir -p "${fresh_project}"
if (
    cd "${fresh_project}"
    "${scbolt}" init missing.mk > "${tmpdir}/fresh-missing-init.out" \
        2> "${tmpdir}/fresh-missing-init.err"
); then
    printf '%s\n' "expected fresh init with missing file to fail" >&2
    exit 1
fi
grep -qx 'Parameter file not found: missing.mk' "${tmpdir}/fresh-missing-init.err"
grep -qx '✗ scBOLT project initialization failed.' "${tmpdir}/fresh-missing-init.err"

empty_project="${tmpdir}/empty-project"
mkdir -p "${empty_project}"
if (
    cd "${empty_project}"
    printf '\n' | "${scbolt}" init > "${tmpdir}/empty-init.out" \
        2> "${tmpdir}/empty-init.err"
); then
    printf '%s\n' "expected fresh init with empty input to fail" >&2
    exit 1
fi
grep -qx 'No parameter file specified.' "${tmpdir}/empty-init.err"
grep -qx '✗ scBOLT project initialization failed.' "${tmpdir}/empty-init.err"

run_scbolt "${project}" bn-submin --params=override.mk
expect_make_args -f "${makefile}" bn-submin PARAMS=override.mk

run_scbolt "${project}" --params=override.mk bn-submin
expect_make_args -f "${makefile}" bn-submin PARAMS=override.mk

run_scbolt "${project}" bn-submin PARAMS=override.mk
expect_make_args -f "${makefile}" bn-submin PARAMS=override.mk

run_scbolt "${project}" PARAMS=override.mk bn-submin
expect_make_args -f "${makefile}" bn-submin PARAMS=override.mk

run_scbolt "${project}" bn-submin --max-clause=12 --clingo-opt-strategy-seed=bb,inc
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    MAX_CLAUSE=12 \
    CLINGO_OPT_STRATEGY_SEED=bb,inc \
    "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" bn-submin --public-dir=shared-public
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    PUBLIC_DIR=shared-public \
    "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" --references="ctrl treated" check velocity --params=params.mk
expect_make_args \
    -f "${makefile}" \
    check \
    TARGET=velocity \
    "REFERENCES=ctrl treated" \
    PARAMS=params.mk

run_scbolt "${project}" check velocity --params=params.mk --references="ctrl treated"
expect_make_args \
    -f "${makefile}" \
    check \
    TARGET=velocity \
    "REFERENCES=ctrl treated" \
    PARAMS=params.mk

run_scbolt "${project}" check --target=velocity --params=params.mk --references ctrl
expect_make_args \
    -f "${makefile}" \
    check \
    TARGET=velocity \
    REFERENCES=ctrl \
    PARAMS=params.mk

run_scbolt "${project}" dry-run bn-submin --params=params.mk
expect_make_args -f "${makefile}" dry-run TARGET=bn-submin PARAMS=params.mk

run_scbolt "${project}" --target bn-submin dry-run --params=params.mk
expect_make_args -f "${makefile}" dry-run TARGET=bn-submin PARAMS=params.mk

run_scbolt "${project}" progress --params=params.mk
expect_make_args -f "${makefile}" progress PARAMS=params.mk

run_scbolt "${project}" progress --all --params=params.mk
expect_make_args -f "${makefile}" progress PROGRESS_ALL=true PARAMS=params.mk

run_scbolt "${project}" progress bn-min bn-diverse --params=params.mk
expect_make_args -f "${makefile}" progress "TARGET=bn-min bn-diverse" PARAMS=params.mk

run_scbolt "${project}" show-config macrostates --params=params.mk
expect_make_args \
    -f "${makefile}" \
    show-config \
    TARGET=macrostates \
    PARAMS=params.mk

run_scbolt "${project}" show-config macrostates --raw --params=params.mk
expect_make_args \
    -f "${makefile}" \
    show-config \
    TARGET=macrostates \
    SHOW_CONFIG_RAW=true \
    PARAMS=params.mk

fallback_project="${tmpdir}/fallback"
mkdir -p "${fallback_project}"
printf '# fallback params\n' > "${fallback_project}/params.mk"
run_scbolt "${fallback_project}" bn-submin
expect_make_args -f "${makefile}" bn-submin PARAMS=params.mk

bad_install="${tmpdir}/bad-install"
mkdir -p "${bad_install}/bin"
cp "${scbolt}" "${bad_install}/bin/scbolt"
chmod +x "${bad_install}/bin/scbolt"
if "${bad_install}/bin/scbolt" help > "${tmpdir}/bad.out" 2> "${tmpdir}/bad.err"; then
    printf '%s\n' "expected corrupted installation check to fail" >&2
    exit 1
fi
grep -q 'Makefile not found' "${tmpdir}/bad.err"

printf '%s\n' "scbolt CLI tests passed"
