#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT
cd "${repo_root}"

for backend in conda mamba micromamba docker; do
    home="${tmpdir}/${backend}/home"
    xdg_config="${tmpdir}/${backend}/config"
    install_bin="${home}/bin"
    mkdir -p "${home}" "${xdg_config}" "${install_bin}"

    HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    SCBOLT_INSTALL_BIN_DIR="${install_bin}" \
        "${repo_root}/install" </dev/null >/dev/null

    installed_launcher="${install_bin}/scbolt"
    test -x "${installed_launcher}"
    HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    SCBOLT_INSTALL_SKIP_IMAGE=true \
        "${installed_launcher}" install "${backend}" \
        --env=__configuration_only__ >/dev/null 2>&1

    config="${xdg_config}/scbolt/config.mk"
    test -f "${config}"
    grep -q "^BACKEND = ${backend}$" "${config}"

    if [ "${backend}" = "docker" ]; then
        version="$(tr -d '[:space:]' < "${repo_root}/VERSION")"
        grep -q "^SCBOLT_IMAGE = ghcr.io/bnediction/scbolt:v${version}$" "${config}"
    else
        ! grep -q '^SCBOLT_IMAGE =' "${config}"
        grep -q "^SCBOLT_ROOT = ${repo_root}$" "${config}"
    fi

    grep -q 'scbolt __complete' \
        "${home}/.local/share/bash-completion/completions/scbolt"

    HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
        "${installed_launcher}" --version >/dev/null
done
