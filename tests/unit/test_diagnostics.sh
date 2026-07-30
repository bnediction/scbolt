#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
scbolt="${repo_root}/bin/scbolt"
tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

mkdir -p \
    "${tmpdir}/bin" \
    "${tmpdir}/envs/scbolt-system" \
    "${tmpdir}/project" \
    "${tmpdir}/resources"
cat > "${tmpdir}/bin/conda" <<EOF
#!/usr/bin/env bash
if [ "\${1:-}" = env ] && [ "\${2:-}" = list ]; then
    printf '%s\n' '${tmpdir}/envs/scbolt-system'
else
    printf '%s\n' 'conda 24.1.0'
fi
EOF
chmod +x "${tmpdir}/bin/conda"

cat > "${tmpdir}/scbolt.yml" <<EOF
backend: conda
project_dir: ${tmpdir}/project
resources_dir: ${tmpdir}/resources
openblas_core_type: Haswell
seed: 7
EOF

PATH="${tmpdir}/bin:${PATH}" \
    "${scbolt}" diagnostics --config="${tmpdir}/scbolt.yml" \
    > "${tmpdir}/ok.out"

for section in \
    scBOLT Host Configuration Backend Runtime "Numerical reproducibility" Status; do
    grep -qx "${section}" "${tmpdir}/ok.out"
done
grep -q '^  ✓ backend: conda$' "${tmpdir}/ok.out"
grep -q '^  ✓ random seed: 7$' "${tmpdir}/ok.out"
grep -q '^  ✓ OpenBLAS core type: Haswell$' "${tmpdir}/ok.out"
! grep -q $'\033' "${tmpdir}/ok.out"

cat > "${tmpdir}/warning.yml" <<EOF
backend: conda
project_dir: ${tmpdir}/project
resources_dir: ${tmpdir}/resources
openblas_core_type: Skylake
EOF
PATH="${tmpdir}/bin:${PATH}" \
    "${scbolt}" diagnostics --config="${tmpdir}/warning.yml" \
    > "${tmpdir}/warning.out"
grep -q '^  ⚠ OpenBLAS core type: Skylake$' "${tmpdir}/warning.out"
grep -q '^  Operational with [0-9][0-9]* warning' "${tmpdir}/warning.out"

mkdir -p "${tmpdir}/outside" "${tmpdir}/home" "${tmpdir}/config"
(
    cd "${tmpdir}/outside"
    HOME="${tmpdir}/home" \
    XDG_CONFIG_HOME="${tmpdir}/config" \
    PATH="${tmpdir}/bin:${PATH}" \
        "${scbolt}" diagnostics > "${tmpdir}/outside.out"
)
grep -q '^  ⚠ configuration file: not selected$' "${tmpdir}/outside.out"
grep -q '^  Operational with [0-9][0-9]* warning' "${tmpdir}/outside.out"

if PATH="${tmpdir}/bin:${PATH}" \
    "${scbolt}" diagnostics --config="${tmpdir}/missing.yml" \
    > "${tmpdir}/missing.out"; then
    printf '%s\n' "expected an explicitly missing configuration to fail" >&2
    exit 1
fi
grep -q '^  ✗ configuration file: .*missing.yml$' "${tmpdir}/missing.out"
test "$(grep -c 'configuration file:' "${tmpdir}/missing.out")" -eq 1

cat > "${tmpdir}/docker.yml" <<EOF
backend: docker
container_engine: unavailable-docker
project_dir: ${tmpdir}/project
resources_dir: ${tmpdir}/resources
openblas_core_type: Haswell
EOF
if PATH="${tmpdir}/bin:${PATH}" \
    "${scbolt}" diagnostics --config="${tmpdir}/docker.yml" \
    > "${tmpdir}/docker.out"; then
    printf '%s\n' "expected unavailable Docker to be a blocking error" >&2
    exit 1
fi
grep -q '^  ✗ Docker CLI: unavailable$' "${tmpdir}/docker.out"
grep -q '^  Not operational: [0-9][0-9]* blocking error' "${tmpdir}/docker.out"

if "${scbolt}" diagnostics unexpected > /dev/null 2>&1; then
    printf '%s\n' "expected invalid diagnostics usage to fail" >&2
    exit 1
else
    test "$?" -eq 2
fi

SCBOLT_TEST_SECRET=not-for-output PATH="${tmpdir}/bin:${PATH}" \
    "${scbolt}" diagnostics --config="${tmpdir}/scbolt.yml" \
    > "${tmpdir}/secret.out"
! grep -q 'not-for-output' "${tmpdir}/secret.out"

printf '%s\n' "diagnostics tests passed"
