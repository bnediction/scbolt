#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"
manager="${tmpdir}/conda"

trap 'rm -rf "${tmpdir}"' EXIT

cat > "${manager}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
    --version)
        printf '%s\n' 'conda 99.0.0'
        ;;
    env)
        test "${2:-}" = list
        printf '%s\n' 'scbolt-system  /tmp/scbolt-system'
        ;;
    *)
        exit 2
        ;;
esac
EOF
chmod +x "${manager}"

run_check() {
    make -C "${repo_root}" check \
        TARGET=load-fastq \
        TRUST_TARGET=load-fastq \
        PARAMS=tests/fixtures/params.mk \
        SCBOLT_ENV_MANAGER="${manager}" \
        "$@"
}

run_check > "${tmpdir}/valid.out"
grep -qx 'Runtime' "${tmpdir}/valid.out"
grep -qx '  ✓ backend: conda' "${tmpdir}/valid.out"
grep -qx '  ✓ environment manager: conda 99.0.0' "${tmpdir}/valid.out"
grep -Eq '^  ✓ GNU Make: [0-9]+([.][0-9]+)+$' "${tmpdir}/valid.out"
grep -Eq '^  ✓ Bash: [0-9]+([.][0-9]+)+$' "${tmpdir}/valid.out"
grep -qx '  ✓ scbolt-system environment: available' "${tmpdir}/valid.out"
grep -qx 'Numerical reproducibility' "${tmpdir}/valid.out"
grep -qx '  ✓ profile: openblas-haswell' "${tmpdir}/valid.out"
grep -Eq '^  (✓|⚠) CPU microarchitecture: ' "${tmpdir}/valid.out"
grep -qx '  ✓ numerical threads: 1' "${tmpdir}/valid.out"

if run_check MAKE_VERSION=4.2 > "${tmpdir}/old-make.out" 2>&1; then
    printf '%s\n' 'expected GNU Make 4.2 diagnostics to fail' >&2
    exit 1
fi
grep -qx '  ✗ GNU Make: 4.2' "${tmpdir}/old-make.out"
grep -q 'GNU Make 4.3 or newer is required' "${tmpdir}/old-make.out"

if run_check __check_bash_version__=3.2.57 > "${tmpdir}/old-bash.out" 2>&1; then
    printf '%s\n' 'expected Bash 3.2 diagnostics to fail' >&2
    exit 1
fi
grep -qx '  ✗ Bash: 3.2.57' "${tmpdir}/old-bash.out"
grep -q 'Bash 4.0 or newer is required' "${tmpdir}/old-bash.out"

printf '%s\n' 'check runtime tests passed'
