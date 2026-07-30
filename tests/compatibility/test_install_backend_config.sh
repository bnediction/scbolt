#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

home="${tmpdir}/cli/home"
xdg_config="${tmpdir}/cli/config"
mkdir -p "${home}" "${xdg_config}"
HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    "${repo_root}/install" >/dev/null
test -L "${home}/.local/bin/scbolt"
test -L "${home}/.local/share/bash-completion/completions/scbolt"
test ! -e "${xdg_config}/scbolt/config.mk"

for backend in conda mamba micromamba docker; do
    home="${tmpdir}/${backend}/home"
    xdg_config="${tmpdir}/${backend}/config"
    mkdir -p "${home}" "${xdg_config}"

    HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
        "${repo_root}/install" --cli --backend="${backend}" >/dev/null

    config="${xdg_config}/scbolt/config.mk"
    test -f "${config}"
    grep -q "^BACKEND = ${backend}$" "${config}"
    test -L "${home}/.local/bin/scbolt"
    test "$(readlink -f "${home}/.local/bin/scbolt")" \
        = "${repo_root}/bin/scbolt"
    test -L "${home}/.local/share/bash-completion/completions/scbolt"
    test "$(readlink -f \
        "${home}/.local/share/bash-completion/completions/scbolt")" \
        = "${repo_root}/bin/completion.bash"

    if [ "${backend}" = "docker" ]; then
        grep -q '^SCBOLT_IMAGE = ghcr.io/bnediction/scbolt:latest$' "${config}"
    else
        ! grep -q '^SCBOLT_IMAGE =' "${config}"
    fi

    PATH="${home}/.local/bin:${PATH}" HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
        scbolt --version >/dev/null
done
