#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

launcher="${tmpdir}/scbolt"
system_prefix="${tmpdir}/scbolt-system"
trace="${tmpdir}/make.trace"
project="${tmpdir}/project"

mkdir -p "${system_prefix}/bin" "${project}"
(
    cd "${repo_root}"
    GOCACHE="${tmpdir}/go-cache" go build \
        -o "${launcher}" \
        ./launcher/scbolt
)

ln -s "$(command -v bash)" "${system_prefix}/bin/bash"
cat > "${system_prefix}/bin/make" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "${trace}"
exec "$(command -v make)" "\$@"
EOF
chmod +x "${system_prefix}/bin/make"

cat > "${project}/.scbolt" <<EOF
PARAMS = ${repo_root}/tests/fixtures/params.mk
EOF

for backend in conda mamba micromamba; do
    output="$(
        cd "${project}"
        SCBOLT_ROOT="${repo_root}" \
        SCBOLT_ENV_MANAGER="$(command -v true)" \
        SCBOLT_SYSTEM_PREFIX="${system_prefix}" \
            "${launcher}" --backend="${backend}" config --default --raw
    )"
    awk -F= '$1 == "BACKEND" { print $2; exit }' <<< "${output}" \
        | grep -qx "${backend}"
done

(
    cd "${project}"
    SCBOLT_ROOT="${repo_root}" \
    SCBOLT_ENV_MANAGER="$(command -v true)" \
    SCBOLT_SYSTEM_PREFIX="${system_prefix}" \
        "${launcher}" check max-nodes-seed __check_externals__=false >/dev/null
)

grep -q -- "-f ${repo_root}/Makefile config DEFAULT_CONFIG=true" "${trace}"
grep -q -- "-f ${repo_root}/Makefile check TARGET=max-nodes-seed" "${trace}"

child_pid_file="${tmpdir}/child.pid"
cat > "${system_prefix}/bin/make" <<EOF
#!/usr/bin/env bash
case "\$*" in
    *__reference-context*|*__finalize-interrupted-gene-selection-results*|*__kept-gene-selection-results*)
        exit 0
        ;;
esac
printf '%s\n' "\$\$" > "${child_pid_file}"
exec sleep 60
EOF
chmod +x "${system_prefix}/bin/make"

set +e
(
    cd "${project}"
    timeout --preserve-status --kill-after=2s --signal=INT 1s \
        env \
        SCBOLT_ROOT="${repo_root}" \
        SCBOLT_ENV_MANAGER="$(command -v true)" \
        SCBOLT_SYSTEM_PREFIX="${system_prefix}" \
        "${launcher}" spec > "${tmpdir}/interrupt.out" 2>&1
)
status="$?"
set -e
test "${status}" -eq 130
test -s "${child_pid_file}"
child_pid="$(cat "${child_pid_file}")"
grep -q 'interrupted by user (spec)' "${tmpdir}/interrupt.out"

for _ in {1..50}; do
    if ! kill -0 "${child_pid}" 2>/dev/null; then
        child_pid=""
        break
    fi
    sleep 0.05
done
if [ -n "${child_pid}" ]; then
    printf 'launcher child process is still running: %s\n' "${child_pid}" >&2
    exit 1
fi

printf '%s\n' "Go local launcher compatibility tests passed"
