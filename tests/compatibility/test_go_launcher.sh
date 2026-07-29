#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

build_dir="${tmpdir}/build"
home_dir="${tmpdir}/home"
launcher="${build_dir}/scbolt-linux-amd64"

make -C "${repo_root}/launcher" \
    GOCACHE="${tmpdir}/go-cache" \
    BUILD_DIR="${build_dir}" \
    linux-amd64 windows-amd64

test -x "${launcher}"
test -f "${build_dir}/scbolt-windows-amd64.exe"

"${launcher}" completion bash > "${tmpdir}/completion.bash"
bash -n "${tmpdir}/completion.bash"

"${launcher}" __complete --index 1 -- scbolt bn > "${tmpdir}/commands"
grep -qx 'bn-min' "${tmpdir}/commands"
grep -qx 'bn-submin' "${tmpdir}/commands"
grep -qx 'bn-diverse' "${tmpdir}/commands"

env \
    HOME="${home_dir}" \
    XDG_CONFIG_HOME="${home_dir}/config" \
    XDG_DATA_HOME="${home_dir}/data" \
    SCBOLT_INSTALL_BIN_DIR="${home_dir}/bin" \
    "${launcher}" </dev/null > "${tmpdir}/bootstrap.out"

installed_launcher="${home_dir}/bin/scbolt"
test -x "${installed_launcher}"
cmp "${launcher}" "${installed_launcher}"
test ! -e "${home_dir}/config/scbolt/config.mk"
test -f "${home_dir}/data/bash-completion/completions/scbolt"
test -f "${home_dir}/data/zsh/site-functions/_scbolt"
test -f "${home_dir}/config/fish/completions/scbolt.fish"
test -f "${home_dir}/data/scbolt/completions/scbolt.ps1"

env \
    HOME="${home_dir}" \
    XDG_CONFIG_HOME="${home_dir}/config" \
    XDG_DATA_HOME="${home_dir}/data" \
    SCBOLT_INSTALL_BIN_DIR="${home_dir}/bin" \
    "${installed_launcher}" > "${tmpdir}/help.out"
grep -q '^usage: scbolt ' "${tmpdir}/help.out"

env \
    HOME="${home_dir}" \
    XDG_CONFIG_HOME="${home_dir}/config" \
    XDG_DATA_HOME="${home_dir}/data" \
    SCBOLT_INSTALL_BIN_DIR="${home_dir}/bin" \
    SCBOLT_INSTALL_SKIP_IMAGE=true \
    "${installed_launcher}" install docker > "${tmpdir}/install.out"

grep -qx 'BACKEND = docker' "${home_dir}/config/scbolt/config.mk"
grep -qx 'SCBOLT_CONTAINER_ENGINE = docker' \
    "${home_dir}/config/scbolt/config.mk"

env \
    HOME="${home_dir}" \
    XDG_CONFIG_HOME="${home_dir}/config" \
    XDG_DATA_HOME="${home_dir}/data" \
    SCBOLT_LAUNCHER_DRY_RUN=true \
    "${installed_launcher}" help > "${tmpdir}/docker-help.out"
grep -q '^usage: scbolt ' "${tmpdir}/docker-help.out"
if grep -q '"docker" "run"' "${tmpdir}/docker-help.out"; then
    printf '%s\n' "top-level help unexpectedly launched Docker" >&2
    exit 1
fi

(
    cd "${tmpdir}"
    env \
        HOME="${home_dir}" \
        XDG_CONFIG_HOME="${home_dir}/config" \
        XDG_DATA_HOME="${home_dir}/data" \
        SCBOLT_LAUNCHER_DRY_RUN=true \
        "${installed_launcher}" bn-submin > "${tmpdir}/docker.out"
)

grep -q '"docker" "run"' "${tmpdir}/docker.out"
grep -q 'ghcr.io/bnediction/scbolt:v' "${tmpdir}/docker.out"
if grep -q 'cannot locate scBOLT root' "${tmpdir}/docker.out"; then
    printf '%s\n' "standalone launcher unexpectedly requires a checkout" >&2
    exit 1
fi

printf '%s\n' "Go launcher compatibility tests passed"
