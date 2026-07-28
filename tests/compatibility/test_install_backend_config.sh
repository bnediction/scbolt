#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

for backend in conda mamba micromamba docker; do
    home="${tmpdir}/${backend}/home"
    xdg_config="${tmpdir}/${backend}/config"
    mkdir -p "${home}" "${xdg_config}"

    HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
        "${repo_root}/install" --cli --backend="${backend}" >/dev/null

    config="${xdg_config}/scbolt/config.mk"
    test -f "${config}"
    grep -q "^BACKEND = ${backend}$" "${config}"

    if [ "${backend}" = "docker" ]; then
        grep -q '^SCBOLT_IMAGE = ghcr.io/bnediction/scbolt:latest$' "${config}"
        test ! -L "${home}/.local/bin/scbolt"
    else
        ! grep -q '^SCBOLT_IMAGE =' "${config}"
        test -L "${home}/.local/bin/scbolt"
        test "$(readlink -f "${home}/.local/bin/scbolt")" \
            = "${repo_root}/build/launcher/scbolt-native"
    fi

    grep -q 'scbolt __complete' \
        "${home}/.local/share/bash-completion/completions/scbolt"

    PATH="${home}/.local/bin:${PATH}" HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
        scbolt --version >/dev/null
done
