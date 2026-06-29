#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

fake_conda="${tmpdir}/conda/bin/conda"
fake_system_bin="${tmpdir}/conda/envs/scbolt-system/bin"
minimal_bin="${tmpdir}/minimal-bin"
tool_log="${tmpdir}/system-tools.log"

mkdir -p "$(dirname "${fake_conda}")" "${fake_system_bin}" "${minimal_bin}"

cat > "${fake_conda}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

case "\${1:-}" in
    --version)
        printf '%s\n' 'conda 0.0-test'
        ;;
    info)
        if [ "\${2:-}" = "--base" ]; then
            printf '%s\n' "${tmpdir}/conda"
        else
            exit 2
        fi
        ;;
    env)
        if [ "\${2:-}" = "list" ]; then
            printf '%s\n' '# conda environments:'
            printf '%-24s %s\n' 'base' "${tmpdir}/conda"
            printf '%-24s %s\n' 'scbolt-system' "${tmpdir}/conda/envs/scbolt-system"
        else
            exit 2
        fi
        ;;
    run)
        shift
        while [ "\$#" -gt 0 ]; do
            case "\$1" in
                --no-capture-output)
                    shift
                    ;;
                -n)
                    shift 2
                    ;;
                *)
                    exec "\$@"
                    ;;
            esac
        done
        ;;
    *)
        exit 2
        ;;
esac
EOF
chmod +x "${fake_conda}"

make_wrapper() {
    local tool="$1"
    local host_tool="$2"

    cat > "${fake_system_bin}/${tool}" <<EOF
#!/usr/bin/env bash
printf '%s\n' "${tool}" >> "${tool_log}"
exec "${host_tool}" "\$@"
EOF
    chmod +x "${fake_system_bin}/${tool}"
}

for tool in awk cat cp date du find grep head id mkdir mktemp realpath rm sed seq sort tail tee timeout touch tr wc wget; do
    make_wrapper "${tool}" "$(type -P "${tool}")"
done

for tool in bash basename dirname env id ln make pwd readlink stty; do
    ln -s "$(type -P "${tool}")" "${minimal_bin}/${tool}"
done
ln -s "${fake_conda}" "${minimal_bin}/conda"

PATH="${minimal_bin}:${repo_root}/bin" \
CONDA_EXE="${fake_conda}" \
HOME="${tmpdir}/home" \
XDG_CONFIG_HOME="${tmpdir}/config" \
SCBOLT_IN_DOCKER=true \
    "${repo_root}/bin/scbolt" config --default --raw >/dev/null

for tool in awk grep sed wget; do
    PATH="${minimal_bin}:${repo_root}/bin" \
    CONDA_EXE="${fake_conda}" \
        "${repo_root}/bin/scbolt-tool" "${tool}" --version >/dev/null
done

grep -q '^awk$' "${tool_log}"
grep -q '^grep$' "${tool_log}"
grep -q '^sed$' "${tool_log}"
grep -q '^wget$' "${tool_log}"
