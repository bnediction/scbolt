#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
backend="${SCBOLT_TEST_BACKEND:-conda}"
skip_install="${SCBOLT_SKIP_ENV_INSTALL:-false}"
output=""

case "${backend}" in
    conda|mamba|micromamba)
        ;;
    *)
        printf 'unsupported test backend: %s\n' "${backend}" >&2
        exit 2
        ;;
esac

if [ "${skip_install}" != "true" ]; then
    "${repo_root}/install" --env=system --backend="${backend}"
fi

output="$("${backend}" run -n scbolt-system awk 'BEGIN { print "scbolt-system ok" }')"
grep -qx 'scbolt-system ok' <<< "${output}"

home="$(mktemp -d)"
xdg_config="$(mktemp -d)"
trap 'rm -rf "${home}" "${xdg_config}"' EXIT

HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    "${repo_root}/install" --cli --backend="${backend}" >/dev/null

PATH="${home}/.local/bin:${PATH}" \
HOME="${home}" \
XDG_CONFIG_HOME="${xdg_config}" \
SCBOLT_IN_DOCKER=true \
    scbolt --version >/dev/null

output="$(
    PATH="${home}/.local/bin:${PATH}" \
    HOME="${home}" \
    XDG_CONFIG_HOME="${xdg_config}" \
    SCBOLT_IN_DOCKER=true \
        scbolt config --default --raw
)"
awk -F= '$1 == "BACKEND" { print $2; exit }' <<< "${output}" \
    | grep -qx "${backend}"
