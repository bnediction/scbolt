#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

source_copy="${tmpdir}/cli/source"
home="${tmpdir}/cli/home"
xdg_config="${tmpdir}/cli/config"
mkdir -p "${source_copy}" "${home}" "${xdg_config}"
for entry in Makefile VERSION install bin envs lib mk scripts; do
    cp -R "${repo_root}/${entry}" "${source_copy}/"
done
HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    "${source_copy}/install" >/dev/null
installed_root="${home}/.local/lib/scbolt"
test -L "${home}/.local/bin/scbolt"
test "$(readlink -f "${home}/.local/bin/scbolt")" \
    = "${installed_root}/bin/scbolt"
test -f "${home}/.local/share/bash-completion/completions/scbolt"
test ! -L "${home}/.local/share/bash-completion/completions/scbolt"
test -f "${installed_root}/Makefile"
test -f "${installed_root}/REVISION"
test -f "${installed_root}/scripts/utils/project_config.py"
test ! -e "${xdg_config}/scbolt/config.mk"
rm -rf "${source_copy}"
PATH="${home}/.local/bin:${PATH}" HOME="${home}" \
    XDG_CONFIG_HOME="${xdg_config}" scbolt --version >/dev/null
mkdir -p "${tmpdir}/cli/project"
(
    cd "${tmpdir}/cli/project"
    PATH="${home}/.local/bin:${PATH}" HOME="${home}" \
        XDG_CONFIG_HOME="${xdg_config}" \
        scbolt config --default --raw >/dev/null
)
if grep -R -Fq "${source_copy}" "${installed_root}"; then
    printf 'installed runtime references removed source: %s\n' \
        "${source_copy}" >&2
    exit 1
fi

home="${tmpdir}/dev/home"
xdg_config="${tmpdir}/dev/config"
mkdir -p "${home}" "${xdg_config}"
HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
    "${repo_root}/install" --dev >/dev/null
test -L "${home}/.local/bin/scbolt"
test "$(readlink -f "${home}/.local/bin/scbolt")" \
    = "${repo_root}/bin/scbolt"
test -L "${home}/.local/share/bash-completion/completions/scbolt"
test "$(readlink -f \
    "${home}/.local/share/bash-completion/completions/scbolt")" \
    = "${repo_root}/bin/completion.bash"
test ! -e "${home}/.local/lib/scbolt"

for backend in conda mamba micromamba docker; do
    home="${tmpdir}/${backend}/home"
    xdg_config="${tmpdir}/${backend}/config"
    mkdir -p "${home}" "${xdg_config}"

    HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
        "${repo_root}/install" --cli --backend="${backend}" >/dev/null

    config="${xdg_config}/scbolt/config.mk"
    installed_root="${home}/.local/lib/scbolt"
    test -f "${config}"
    grep -q "^BACKEND = ${backend}$" "${config}"
    test -L "${home}/.local/bin/scbolt"
    test "$(readlink -f "${home}/.local/bin/scbolt")" \
        = "${installed_root}/bin/scbolt"
    test -f "${home}/.local/share/bash-completion/completions/scbolt"
    test ! -L "${home}/.local/share/bash-completion/completions/scbolt"

    if [ "${backend}" = "docker" ]; then
        grep -q '^SCBOLT_IMAGE = ghcr.io/bnediction/scbolt:latest$' "${config}"
    else
        ! grep -q '^SCBOLT_IMAGE =' "${config}"
    fi

    PATH="${home}/.local/bin:${PATH}" HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
        scbolt --version >/dev/null
done
