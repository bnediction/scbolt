#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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
status="${SCBOLT_TEST_MAKE_STATUS:-0}"
for arg in "$@"; do
    if [ "${arg}" = "__reference-context" ]; then
        references="${SCBOLT_TEST_REFERENCES:-}"
        if [ -z "${references}" ]; then
            for make_arg in "$@"; do
                case "${make_arg}" in
                    REFERENCES=*)
                        references="${make_arg#REFERENCES=}"
                        ;;
                esac
            done
        fi
        references="${references:-${SCBOLT_TEST_FULL_REFERENCES:-ctrl treated integrated}}"
        printf 'REFERENCES=%s\n' "${references}"
        printf 'REFERENCES_DEFAULT=%s\n' "${SCBOLT_TEST_FULL_REFERENCES:-ctrl treated integrated}"
        exit 0
    fi
    case "${arg}" in
        __intermediate-gene-selection-status)
            if [ -n "${SCBOLT_TEST_INTERMEDIATE_STATUS:-}" ]; then
                printf '%s\n' "${SCBOLT_TEST_INTERMEDIATE_STATUS}"
            fi
            exit 0
            ;;
        __finalize-interrupted-gene-selection-results)
            exit 0
            ;;
        __kept-gene-selection-results)
            if [ -n "${SCBOLT_TEST_KEPT_RESULT:-}" ]; then
                printf '%s\n' "${SCBOLT_TEST_KEPT_RESULT}"
            fi
            exit 0
            ;;
    esac
done
printf '%s\n' "$@" > "${SCBOLT_TEST_RECORD}"
if [ -n "${SCBOLT_TEST_MAKE_STDOUT:-}" ]; then
    printf '%s\n' "${SCBOLT_TEST_MAKE_STDOUT}"
fi
if [ -n "${SCBOLT_TEST_MAKE_STDOUT_RAW:-}" ]; then
    printf '%s' "${SCBOLT_TEST_MAKE_STDOUT_RAW}"
fi
case "${status}" in
    0) ;;
    124|130|143)
        printf 'make: *** [mk/cli.mk:999: %s] Error %s\n' "${2:-target}" "${status}" >&2
        ;;
    *)
        printf '%s\n' "${SCBOLT_TEST_MAKE_STDERR:-real underlying error}" >&2
        printf 'make: *** [mk/cli.mk:999: %s] Error %s\n' "${2:-target}" "${status}" >&2
        ;;
esac
exit "${status}"
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

complete_scbolt() {
    local project_dir="$1"
    local cword="$2"
    shift 2

    (
        cd "${project_dir}"
        PATH="${repo_root}/bin:${PATH}"
        source "${repo_root}/bin/completion.bash"
        COMP_WORDS=("$@")
        COMP_CWORD="${cword}"
        COMP_LINE="${COMP_WORDS[*]}"
        if [ -z "${COMP_WORDS[COMP_CWORD]}" ]; then
            COMP_LINE="${COMP_LINE} "
        fi
        COMP_POINT="${#COMP_LINE}"
        _scbolt
        printf '%s\n' "${COMPREPLY[@]}"
    )
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
    expect_make_args -f "${makefile}" help SCBOLT_CLI=true PARAMS=params.mk
done

run_scbolt_from_path "${project}" help
expect_make_args -f "${makefile}" help SCBOLT_CLI=true PARAMS=params.mk

run_scbolt "${project}" config help
expect_make_args -f "${makefile}" config HELP=true SCBOLT_CLI=true PARAMS=params.mk

run_scbolt "${project}" config -h
expect_make_args -f "${makefile}" config HELP=true SCBOLT_CLI=true PARAMS=params.mk

run_scbolt "${project}" config --help
expect_make_args -f "${makefile}" config HELP=true SCBOLT_CLI=true PARAMS=params.mk

run_scbolt "${project}" config --default
expect_make_args -f "${makefile}" config DEFAULT_CONFIG=true

run_scbolt "${project}" config --default --raw
expect_make_args -f "${makefile}" config DEFAULT_CONFIG=true CONFIG_RAW=true

run_scbolt "${project}" check --help
expect_make_args -f "${makefile}" check HELP=true SCBOLT_CLI=true PARAMS=params.mk

run_scbolt "${project}" check
expect_make_args -f "${makefile}" check PARAMS=params.mk

run_scbolt "${project}" dry-run help
expect_make_args -f "${makefile}" dry-run HELP=true SCBOLT_CLI=true PARAMS=params.mk

if run_scbolt "${project}" dry-run > "${tmpdir}/missing-dry-run.out" \
    2> "${tmpdir}/missing-dry-run.err"; then
    printf '%s\n' "expected dry-run without module to fail" >&2
    exit 1
fi
test ! -e "${record}"
grep -qx '✗ Missing module for scbolt dry-run.' "${tmpdir}/missing-dry-run.err"
grep -qx 'Usage: scbolt dry-run <module>' "${tmpdir}/missing-dry-run.err"
grep -qx "Run 'scbolt dry-run --help' for details." "${tmpdir}/missing-dry-run.err"

if run_scbolt "${project}" confi > "${tmpdir}/bad-command.out" \
    2> "${tmpdir}/bad-command.err"; then
    printf '%s\n' "expected misspelled command to fail" >&2
    exit 1
fi
test ! -e "${record}"
grep -qx '✗ failed: confi' "${tmpdir}/bad-command.err"
grep -qx 'did you mean: scbolt config' "${tmpdir}/bad-command.err"

if run_scbolt "${project}" bn-submi > "${tmpdir}/bad-module.out" \
    2> "${tmpdir}/bad-module.err"; then
    printf '%s\n' "expected misspelled module to fail" >&2
    exit 1
fi
test ! -e "${record}"
grep -qx '✗ failed: bn-submi' "${tmpdir}/bad-module.err"
grep -qx 'did you mean: scbolt bn-submin' "${tmpdir}/bad-module.err"

if run_scbolt "${project}" clustring > "${tmpdir}/bad-internal-typo.out" \
    2> "${tmpdir}/bad-internal-typo.err"; then
    printf '%s\n' "expected internally misspelled module to fail" >&2
    exit 1
fi
test ! -e "${record}"
grep -qx '✗ failed: clustring' "${tmpdir}/bad-internal-typo.err"
grep -qx 'did you mean: scbolt clustering' "${tmpdir}/bad-internal-typo.err"

if run_scbolt "${project}" dryrun > "${tmpdir}/bad-hyphen-command.out" \
    2> "${tmpdir}/bad-hyphen-command.err"; then
    printf '%s\n' "expected command with missing hyphen to fail" >&2
    exit 1
fi
test ! -e "${record}"
grep -qx '✗ failed: dryrun' "${tmpdir}/bad-hyphen-command.err"
grep -qx 'did you mean: scbolt dry-run' "${tmpdir}/bad-hyphen-command.err"

if run_scbolt "${project}" bn_submin > "${tmpdir}/bad-underscore-module.out" \
    2> "${tmpdir}/bad-underscore-module.err"; then
    printf '%s\n' "expected module with underscore to fail" >&2
    exit 1
fi
test ! -e "${record}"
grep -qx '✗ failed: bn_submin' "${tmpdir}/bad-underscore-module.err"
grep -qx 'did you mean: scbolt bn-submin' "${tmpdir}/bad-underscore-module.err"

if run_scbolt "${project}" config --ra > "${tmpdir}/bad-config-option.out" \
    2> "${tmpdir}/bad-config-option.err"; then
    printf '%s\n' "expected misspelled config option to fail" >&2
    exit 1
fi
test ! -e "${record}"
grep -qx '✗ Unsupported scbolt option: --ra' "${tmpdir}/bad-config-option.err"
grep -qx 'did you mean: scbolt config --raw' "${tmpdir}/bad-config-option.err"

if run_scbolt "${project}" clean --stal > "${tmpdir}/bad-clean-option.out" \
    2> "${tmpdir}/bad-clean-option.err"; then
    printf '%s\n' "expected misspelled clean option to fail" >&2
    exit 1
fi
test ! -e "${record}"
grep -qx '✗ Unsupported scbolt option: --stal' "${tmpdir}/bad-clean-option.err"
grep -qx 'did you mean: scbolt clean --stale' "${tmpdir}/bad-clean-option.err"

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
expect_make_args -f "${makefile}" progress HELP=true SCBOLT_CLI=true PARAMS=params.mk

run_scbolt "${project}" clean help
expect_make_args -f "${makefile}" clean HELP=true SCBOLT_CLI=true PARAMS=params.mk

(
    cd "${project}"
    "${scbolt}" init --help > "${tmpdir}/init-help.out"
)
grep -qx 'usage: scbolt init \[<params.mk>\] \[options\]' "${tmpdir}/init-help.out"
grep -q '^Parameters$' "${tmpdir}/init-help.out"
grep -q '^  --remove' "${tmpdir}/init-help.out"
grep -q '^  --show' "${tmpdir}/init-help.out"
grep -q '^  <parameter>=<value>' "${tmpdir}/init-help.out"
! grep -q -- '-h' "${tmpdir}/init-help.out"

complete_scbolt "${project}" 2 scbolt init "" > "${tmpdir}/init-completion-before.out"
grep -qx -- '--show' "${tmpdir}/init-completion-before.out"
grep -qx -- '--remove' "${tmpdir}/init-completion-before.out"
grep -qx 'params.mk' "${tmpdir}/init-completion-before.out"
! grep -qx -- '--params=' "${tmpdir}/init-completion-before.out"
! grep -qx -- '--organism=' "${tmpdir}/init-completion-before.out"

complete_scbolt "${project}" 3 scbolt init params.mk "" \
    > "${tmpdir}/init-completion-after.out"
! grep -qx -- '--show' "${tmpdir}/init-completion-after.out"
! grep -qx -- '--remove' "${tmpdir}/init-completion-after.out"
grep -qx -- '--organism=' "${tmpdir}/init-completion-after.out"

complete_scbolt "${project}" 3 scbolt init --params=params.mk "" \
    > "${tmpdir}/init-completion-after-params.out"
! grep -qx -- '--show' "${tmpdir}/init-completion-after-params.out"
! grep -qx -- '--remove' "${tmpdir}/init-completion-after-params.out"
grep -qx -- '--organism=' "${tmpdir}/init-completion-after-params.out"

complete_scbolt "${project}" 2 scbolt config "" > "${tmpdir}/config-completion.out"
grep -qx -- '--default' "${tmpdir}/config-completion.out"
grep -qx -- '--raw' "${tmpdir}/config-completion.out"

complete_scbolt "${project}" 2 scbolt bn-submin "" \
    > "${tmpdir}/module-completion.out"
grep -qx -- '--trust-target=' "${tmpdir}/module-completion.out"
grep -qx -- '--trust-existing' "${tmpdir}/module-completion.out"
grep -qx -- '--max-clauses=' "${tmpdir}/module-completion.out"
! grep -qx -- '--trust-existing=' "${tmpdir}/module-completion.out"
! grep -qx -- '--max-clause=' "${tmpdir}/module-completion.out"
! grep -qx -- '--canonical-filter=' "${tmpdir}/module-completion.out"
! grep -qx -- '--canonical-infer=' "${tmpdir}/module-completion.out"

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

rm "${project}/spaced.mk"
(
    cd "${project}"
    printf '\n' | "${scbolt}" init \
        > "${tmpdir}/recreate-init.out" \
        2> "${tmpdir}/recreate-init.err"
)
grep -qx 'PARAMS=spaced.mk' "${project}/.scbolt"
test -f "${project}/spaced.mk"
grep -q '^Parameter file: spaced.mk (created)$' "${tmpdir}/recreate-init.out"
grep -qx '✓ scBOLT project updated.' "${tmpdir}/recreate-init.out"

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

(
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_MAKE_STDOUT='2026-01-01 00:00:00.000 - RULE - bn-submin' \
        "${scbolt}" bn-submin > "${tmpdir}/module-success.out"
)
expect_make_args -f "${makefile}" bn-submin "PARAMS=${project}/spaced.mk"
grep -qx '✓ completed: bn-submin' "${tmpdir}/module-success.out"

run_scbolt "${project}" bn-min > "${tmpdir}/module-up-to-date.out"
expect_make_args -f "${makefile}" bn-min "PARAMS=${project}/spaced.mk"
grep -qx '⚠ up to date: bn-min' "${tmpdir}/module-up-to-date.out"

(
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_INTERMEDIATE_STATUS='intermediate solution: 188/197' \
        "${scbolt}" spec > "${tmpdir}/spec-up-to-date.out"
)
grep -qx '⚠ up to date: spec' "${tmpdir}/spec-up-to-date.out"

(
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_INTERMEDIATE_STATUS='intermediate solution: 188/197' \
        "${scbolt}" max-nodes-lock > "${tmpdir}/lock-up-to-date.out"
)
grep -qx '⚠ up to date: max-nodes-lock (intermediate solution: 188/197)' \
    "${tmpdir}/lock-up-to-date.out"

(
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_MAKE_STDOUT='2026-01-01 00:00:00.000 - WARNING - stale module output: clustering (RESOLUTION: 0.40 -> 0.44)' \
        "${scbolt}" clustering > "${tmpdir}/module-already-built.out"
)
expect_make_args -f "${makefile}" clustering "PARAMS=${project}/spaced.mk"
grep -qx '⚠ already built: clustering' "${tmpdir}/module-already-built.out"

if (
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_MAKE_STATUS=130 \
        "${scbolt}" stream > "${tmpdir}/module-interrupted.out" \
        2> "${tmpdir}/module-interrupted.err"
); then
    printf '%s\n' "expected interrupted module execution to fail" >&2
    exit 1
fi
grep -qx '⚠ interrupted by user (stream)' "${tmpdir}/module-interrupted.out"
! grep -q '^make.*\*\*\*' "${tmpdir}/module-interrupted.err"

if (
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_MAKE_STATUS=130 \
        SCBOLT_TEST_MAKE_STDOUT='2026-01-01 00:00:00.000 - RULE - max-nodes-soft' \
        SCBOLT_TEST_KEPT_RESULT='max-nodes-soft partial (447/5198)' \
        "${scbolt}" max-nodes-soft > "${tmpdir}/module-partial-direct.out" \
        2> "${tmpdir}/module-partial-direct.err"
); then
    printf '%s\n' "expected interrupted gene selection to fail" >&2
    exit 1
fi
grep -qx '⚠ interrupted by user (max-nodes-soft)' \
    "${tmpdir}/module-partial-direct.out"
grep -qx '✓ kept partial solution: 447/5198' \
    "${tmpdir}/module-partial-direct.out"

if (
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_MAKE_STATUS=130 \
        SCBOLT_TEST_MAKE_STDOUT='2026-01-01 00:00:00.000 - RULE - max-nodes-soft' \
        SCBOLT_TEST_KEPT_RESULT='max-nodes-soft partial (447/5198)' \
        "${scbolt}" bn-submin > "${tmpdir}/module-partial-nested.out" \
        2> "${tmpdir}/module-partial-nested.err"
); then
    printf '%s\n' "expected interrupted aggregate target to fail" >&2
    exit 1
fi
grep -qx '⚠ interrupted by user (bn-submin)' \
    "${tmpdir}/module-partial-nested.out"
grep -qx '✓ kept partial solution (max-nodes-soft): 447/5198' \
    "${tmpdir}/module-partial-nested.out"

if (
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_MAKE_STATUS=130 \
        SCBOLT_TEST_MAKE_STDOUT_RAW='Found 0/100 solutions' \
        "${scbolt}" bn-submin > "${tmpdir}/module-progress-interrupted.out" \
        2> "${tmpdir}/module-progress-interrupted.err"
); then
    printf '%s\n' "expected interrupted progress execution to fail" >&2
    exit 1
fi
grep -qx 'Found 0/100 solutions' "${tmpdir}/module-progress-interrupted.out"
grep -qx '⚠ interrupted by user (bn-submin)' \
    "${tmpdir}/module-progress-interrupted.out"
! grep -q 'solutions⚠' "${tmpdir}/module-progress-interrupted.out"

if (
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_MAKE_STATUS=2 \
        SCBOLT_TEST_MAKE_STDERR=Interrupt \
        "${scbolt}" stream > "${tmpdir}/module-generic-interrupted.out" \
        2> "${tmpdir}/module-generic-interrupted.err"
); then
    printf '%s\n' "expected generic interrupted module execution to fail" >&2
    exit 1
fi
grep -qx '⚠ interrupted by user (stream)' "${tmpdir}/module-generic-interrupted.out"
! grep -q '^make.*\*\*\*' "${tmpdir}/module-generic-interrupted.err"

if (
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_MAKE_STATUS=124 \
        "${scbolt}" max-nodes-seed > "${tmpdir}/module-timeout.out" \
        2> "${tmpdir}/module-timeout.err"
); then
    printf '%s\n' "expected timed-out module execution to fail" >&2
    exit 1
fi
grep -qx '⚠ reached time limit: max-nodes-seed' "${tmpdir}/module-timeout.out"
! grep -q '^make.*\*\*\*' "${tmpdir}/module-timeout.err"

if (
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_MAKE_STATUS=2 \
        "${scbolt}" stream > "${tmpdir}/module-failed.out" \
        2> "${tmpdir}/module-failed.err"
); then
    printf '%s\n' "expected failed module execution to fail" >&2
    exit 1
fi
grep -qx 'real underlying error' "${tmpdir}/module-failed.err"
grep -qx '✗ failed: stream' "${tmpdir}/module-failed.err"
! grep -q '^make.*\*\*\*' "${tmpdir}/module-failed.err"

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

(
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_MAKE_STDOUT='2026-01-01 00:00:00.000 - RULE - stream' \
        "${scbolt}" stream --references=ctrl > "${tmpdir}/module-reference.out"
)
expect_make_args \
    -f "${makefile}" \
    stream \
    REFERENCES=ctrl \
    "PARAMS=${project}/spaced.mk"
grep -qx '✓ completed: stream (ctrl)' "${tmpdir}/module-reference.out"

(
    cd "${project}"
    PATH="${fakebin}:${PATH}" \
        SCBOLT_TEST_RECORD="${record}" \
        SCBOLT_TEST_MAKE_STDOUT='2026-01-01 00:00:00.000 - RULE - stream' \
        "${scbolt}" stream --references="ctrl treated integrated" \
        > "${tmpdir}/module-full-reference.out"
)
expect_make_args \
    -f "${makefile}" \
    stream \
    "REFERENCES=ctrl treated integrated" \
    "PARAMS=${project}/spaced.mk"
grep -qx '✓ completed: stream' "${tmpdir}/module-full-reference.out"

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
(
    cd "${fresh_project}"
    "${scbolt}" init missing.mk > "${tmpdir}/fresh-missing-init.out" \
        2> "${tmpdir}/fresh-missing-init.err"
)
grep -qx 'PARAMS=missing.mk' "${fresh_project}/.scbolt"
test -f "${fresh_project}/missing.mk"
grep -q '^### Project settings ###$' "${fresh_project}/missing.mk"
grep -q '^### Input sources ###$' "${fresh_project}/missing.mk"
grep -q '^### Module-specific inputs ###$' "${fresh_project}/missing.mk"
grep -q '^# Input sources are mutually exclusive\. Use one family:$' \
    "${fresh_project}/missing.mk"
grep -q '^# - SRA or SRA_<CONDITION>   : list of SRA run IDs$' \
    "${fresh_project}/missing.mk"
grep -q '^# - GSM or GSM_<CONDITION>   : GEO sample ID$' \
    "${fresh_project}/missing.mk"
grep -q '^# SRA = SRR12345678 SRR87654321$' "${fresh_project}/missing.mk"
grep -q '^# GSM = GSM5492245$' "${fresh_project}/missing.mk"
! grep -q 'SRA_UNIQUE' "${fresh_project}/missing.mk"
! grep -q 'GSM_UNIQUE' "${fresh_project}/missing.mk"
grep -q '^CONDITIONS =$' "${fresh_project}/missing.mk"
grep -q '^ORGANISM =$' "${fresh_project}/missing.mk"
grep -q '^SRA =$' "${fresh_project}/missing.mk"
grep -q '^GSM =$' "${fresh_project}/missing.mk"
grep -q '^LABEL =$' "${fresh_project}/missing.mk"
grep -q '^SPEC_FILE =$' "${fresh_project}/missing.mk"
grep -q '^COUNT_FILES =$' "${fresh_project}/missing.mk"
grep -q '^MACROSTATE_FILES =$' "${fresh_project}/missing.mk"
grep -q '^BINARIZATION_FILE =$' "${fresh_project}/missing.mk"
grep -qx 'Parameter file: missing.mk (created)' "${tmpdir}/fresh-missing-init.out"
grep -qx '✓ scBOLT project initialized.' "${tmpdir}/fresh-missing-init.out"

filled_project="${tmpdir}/filled-project"
mkdir -p "${filled_project}"
(
    cd "${filled_project}"
    "${scbolt}" init --params=filled.mk \
        --conditions="ctrl treated" \
        --organism=mouse \
        --gsm-ctrl=GSM5492245 \
        --old-file=trusted.h5ad \
        --project-dir=results \
        RESOLUTION=0.46 \
        > "${tmpdir}/filled-init.out" \
        2> "${tmpdir}/filled-init.err"
)
grep -qx 'PARAMS=filled.mk' "${filled_project}/.scbolt"
test -f "${filled_project}/filled.mk"
grep -q '^CONDITIONS = ctrl treated$' "${filled_project}/filled.mk"
grep -q '^ORGANISM = mouse$' "${filled_project}/filled.mk"
grep -q '^SRA_CTRL =$' "${filled_project}/filled.mk"
grep -q '^SRA_TREATED =$' "${filled_project}/filled.mk"
grep -q '^GSM_CTRL = GSM5492245$' "${filled_project}/filled.mk"
grep -q '^GSM_TREATED =$' "${filled_project}/filled.mk"
! grep -q '^SRA =$' "${filled_project}/filled.mk"
! grep -q '^GSM =$' "${filled_project}/filled.mk"
grep -q '^PROJECT_DIR = results$' "${filled_project}/filled.mk"
grep -q '^OLD_FILES = trusted.h5ad$' "${filled_project}/filled.mk"
grep -q '^RESOLUTION = 0.46$' "${filled_project}/filled.mk"
! grep -q '^### User-defined parameters ###$' "${filled_project}/filled.mk"
project_settings_line="$(grep -n '^### Project settings ###$' "${filled_project}/filled.mk" | cut -d: -f1)"
input_sources_line="$(grep -n '^### Input sources ###$' "${filled_project}/filled.mk" | cut -d: -f1)"
module_inputs_line="$(grep -n '^### Module-specific inputs ###$' "${filled_project}/filled.mk" | cut -d: -f1)"
project_dir_line="$(grep -n '^PROJECT_DIR = results$' "${filled_project}/filled.mk" | cut -d: -f1)"
old_files_line="$(grep -n '^OLD_FILES = trusted.h5ad$' "${filled_project}/filled.mk" | cut -d: -f1)"
resolution_line="$(grep -n '^RESOLUTION = 0.46$' "${filled_project}/filled.mk" | cut -d: -f1)"
test "${project_settings_line}" -lt "${project_dir_line}"
test "${project_dir_line}" -lt "${input_sources_line}"
test "${input_sources_line}" -lt "${old_files_line}"
test "${old_files_line}" -lt "${module_inputs_line}"
test "${module_inputs_line}" -lt "${resolution_line}"
grep -qx 'Parameter file: filled.mk (created)' "${tmpdir}/filled-init.out"
grep -qx '✓ scBOLT project initialized.' "${tmpdir}/filled-init.out"

missing_dir_project="${tmpdir}/missing-dir-project"
mkdir -p "${missing_dir_project}"
if (
    cd "${missing_dir_project}"
    "${scbolt}" init missing/params.mk > "${tmpdir}/missing-dir-init.out" \
        2> "${tmpdir}/missing-dir-init.err"
); then
    printf '%s\n' "expected init with missing parent directory to fail" >&2
    exit 1
fi
grep -qx 'Parameter file directory not found: missing' "${tmpdir}/missing-dir-init.err"
grep -qx '✗ scBOLT project initialization failed.' "${tmpdir}/missing-dir-init.err"

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

run_scbolt "${project}" bn-submin --max-clauses=12 --clingo-strategy-seed=bb,inc
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    MAX_CLAUSES=12 \
    CLINGO_STRATEGY_SEED=bb,inc \
    "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" bn-submin --resources-dir=shared-resources
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    RESOURCES_DIR=shared-resources \
    "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" bn-submin --project-dir=shared-project
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    PROJECT_DIR=shared-project \
    "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" bn-submin reset_target=clustering --reset-target=annotation \
    --reset-target velocity
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    RESET_TARGET=clustering \
    CLI_RESET_TARGETS+=annotation \
    CLI_RESET_TARGETS+=velocity \
    "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" bn-submin 'RESET_TARGET=clustering annotation' \
    '--reset-target=velocity potency'
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    "RESET_TARGET=clustering annotation" \
    "CLI_RESET_TARGETS+=velocity potency" \
    "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" bn-submin TRUST_TARGET=clustering --trust-target=annotation \
    --trust-target velocity
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    TRUST_TARGET=clustering \
    CLI_TRUST_TARGETS+=annotation \
    CLI_TRUST_TARGETS+=velocity \
    "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" bn-submin 'TRUST_TARGET=clustering annotation' \
    '--trust-target=velocity potency'
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    "TRUST_TARGET=clustering annotation" \
    "CLI_TRUST_TARGETS+=velocity potency" \
    "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" bn-submin --trust-existing
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    TRUST_EXISTING=true \
    "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" --trust-existing bn-submin
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    TRUST_EXISTING=true \
    "PARAMS=${project}/spaced.mk"

run_scbolt "${project}" trust_existing=false bn-submin
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    TRUST_EXISTING=false \
    "PARAMS=${project}/spaced.mk"

if run_scbolt "${project}" bn-submin --trust-existing=true \
    > "${tmpdir}/trust-existing-value.out" \
    2> "${tmpdir}/trust-existing-value.err"; then
    printf '%s\n' "expected --trust-existing with a value to fail" >&2
    exit 1
fi
test ! -e "${record}"
grep -qx \
    '✗ Unsupported scbolt option with value: --trust-existing' \
    "${tmpdir}/trust-existing-value.err"
grep -qx \
    "Use '--trust-existing' without a value." \
    "${tmpdir}/trust-existing-value.err"

run_scbolt "${project}" bn-submin 'old_files=file1.h5ad file2.csv' \
    '--old-file=file3.h5ad file4.csv' old_file=file5.txt
expect_make_args \
    -f "${makefile}" \
    bn-submin \
    "OLD_FILES=file1.h5ad file2.csv" \
    "CLI_OLD_FILES+=file3.h5ad file4.csv" \
    CLI_OLD_FILES+=file5.txt \
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

run_scbolt "${project}" config macrostates --params=params.mk
expect_make_args \
    -f "${makefile}" \
    config \
    TARGET=macrostates \
    PARAMS=params.mk

run_scbolt "${project}" config macrostates --raw --params=params.mk
expect_make_args \
    -f "${makefile}" \
    config \
    TARGET=macrostates \
    CONFIG_RAW=true \
    PARAMS=params.mk

run_scbolt "${project}" config macrostates --default --raw
expect_make_args \
    -f "${makefile}" \
    config \
    DEFAULT_CONFIG=true \
    TARGET=macrostates \
    CONFIG_RAW=true

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
