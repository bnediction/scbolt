#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

backend_from_config() {
    local expected="$1"
    local output
    shift

    output="$(SCBOLT_IN_DOCKER=true "$@")"
    awk -F= '$1 == "BACKEND" { print $2; exit }' <<< "${output}" \
        | grep -qx "${expected}"
}

home="${tmpdir}/home"
xdg_config="${tmpdir}/config"
mkdir -p "${home}" "${xdg_config}/scbolt"

# Default backend.
backend_from_config conda \
    env HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    "${repo_root}/bin/scbolt" config --default --raw

# User configuration overrides defaults.
printf 'BACKEND = docker\n' > "${xdg_config}/scbolt/config.mk"
backend_from_config docker \
    env HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    "${repo_root}/bin/scbolt" config --default --raw

# params.mk overrides user configuration.
params="${tmpdir}/params.mk"
cp "${repo_root}/tests/fixtures/params.mk" "${params}"
printf '\nBACKEND = micromamba\n' >> "${params}"
backend_from_config micromamba \
    env HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    "${repo_root}/bin/scbolt" config --raw --params="${params}"

# CLI overrides params.mk and user configuration.
backend_from_config mamba \
    env HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    "${repo_root}/bin/scbolt" config --raw --params="${params}" --backend=mamba

# Make-style CLI assignment also overrides params.mk and user configuration.
backend_from_config conda \
    env HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    "${repo_root}/bin/scbolt" config --raw --params="${params}" BACKEND=conda
