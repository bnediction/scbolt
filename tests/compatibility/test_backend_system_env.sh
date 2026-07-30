#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
launcher="${repo_root}/dist/scbolt-linux-amd64"
backend="${SCBOLT_TEST_BACKEND:-conda}"
skip_install="${SCBOLT_SKIP_ENV_INSTALL:-false}"
output=""

cd "${repo_root}"

case "${backend}" in
    conda|mamba|micromamba)
        ;;
    *)
        printf 'unsupported test backend: %s\n' "${backend}" >&2
        exit 2
        ;;
esac

if [ "${skip_install}" != "true" ]; then
    "${launcher}" install "${backend}" --env=system
fi

output="$("${backend}" run -n scbolt-system awk 'BEGIN { print "scbolt-system ok" }')"
grep -qx 'scbolt-system ok' <<< "${output}"

home="$(mktemp -d)"
xdg_config="$(mktemp -d)"
trap 'rm -rf "${home}" "${xdg_config}"' EXIT

HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
SCBOLT_INSTALL_BIN_DIR="${home}/.local/bin" \
    "${repo_root}/install" </dev/null >/dev/null

HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    "${home}/.local/bin/scbolt" install "${backend}" \
    --env=__configuration_only__ >/dev/null 2>&1

PATH="${home}/.local/bin:${PATH}" \
HOME="${home}" \
XDG_CONFIG_HOME="${xdg_config}" \
    scbolt --version >/dev/null

output="$(
    PATH="${home}/.local/bin:${PATH}" \
    HOME="${home}" \
    XDG_CONFIG_HOME="${xdg_config}" \
        scbolt config --default --raw
)"
awk -F= '$1 == "BACKEND" { print $2; exit }' <<< "${output}" \
    | grep -qx "${backend}"
