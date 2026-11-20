#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"
scbolt_version="$(tr -d '[:space:]' < "${repo_root}/VERSION")"

trap 'rm -rf "${tmpdir}"' EXIT

source_copy="${tmpdir}/cli/source"
home="${tmpdir}/cli/home"
xdg_config="${tmpdir}/cli/config"
mkdir -p "${source_copy}" "${home}" "${xdg_config}"
for entry in Makefile VERSION install bin envs lib make scripts; do
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
        grep -q "^SCBOLT_IMAGE = ghcr.io/bnediction/scbolt:${scbolt_version}$" \
            "${config}"
    else
        ! grep -q '^SCBOLT_IMAGE =' "${config}"
    fi

    PATH="${home}/.local/bin:${PATH}" HOME="${home}" XDG_CONFIG_HOME="${xdg_config}" \
        scbolt --version >/dev/null
done

fake_engine="${tmpdir}/fake-container-engine"
container_log="${tmpdir}/container-arguments"
mount_path="${tmpdir}/additional-mount"
mkdir -p "${mount_path}"
cat > "${fake_engine}" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
    image)
        case "$*" in
            *org.opencontainers.image.version*)
                printf '%s\n' "${SCBOLT_TEST_IMAGE_VERSION:-}"
                ;;
            *'{{.Id}}'*)
                printf '%s\n' 'sha256:test'
                ;;
        esac
        exit 0
        ;;
    run)
        printf '%s\n' "$@" > "${SCBOLT_TEST_CONTAINER_LOG}"
        exit 0
        ;;
esac

exit 1
SH
chmod +x "${fake_engine}"

docker_test_home="${tmpdir}/docker-runtime/home"
docker_test_config="${tmpdir}/docker-runtime/config"
mkdir -p "${docker_test_home}" "${docker_test_config}/scbolt"
scbolt_command="${repo_root}/bin/scbolt"
image_version="${scbolt_version}"

run_docker_config() {
    HOME="${docker_test_home}" XDG_CONFIG_HOME="${docker_test_config}" \
    SCBOLT_TEST_CONTAINER_LOG="${container_log}" \
    SCBOLT_TEST_IMAGE_VERSION="${image_version}" \
        "${scbolt_command}" config --default --raw \
        --backend=docker --container-engine="${fake_engine}" "$@"
}

run_docker_config --container-image="scbolt:${scbolt_version}" \
    --container-args=--network=none \
    --container-mounts="${mount_path}"
grep -Fxq -- 'run' "${container_log}"
grep -Fxq -- '--network=none' "${container_log}"
grep -Fxq -- "${mount_path}:${mount_path}" "${container_log}"
grep -Fxq -- "SCBOLT_IMAGE=scbolt:${scbolt_version}" "${container_log}"
grep -Fxq -- 'sha256:test' "${container_log}"

for image_version in 0.0.0 99.0.0 '' '<no value>' unknown; do
    rm -f "${container_log}"
    if run_docker_config --container-image="scbolt:${scbolt_version}" \
            > "${tmpdir}/image-version.out" 2>&1; then
        printf 'unexpectedly accepted image version: %s\n' "${image_version}" >&2
        exit 1
    fi
    grep -Fq "Docker image version mismatch: scBOLT ${scbolt_version}, image" \
        "${tmpdir}/image-version.out"
    test ! -e "${container_log}"
done

# Images selected by the project or installed configuration follow the same rule.
image_version=0.0.0
printf '%s\n' 'container-image: scbolt:0.0.0' > "${tmpdir}/docker.yml"
if run_docker_config --config="${tmpdir}/docker.yml" \
        > "${tmpdir}/project-image.out" 2>&1; then
    printf '%s\n' 'unexpectedly accepted incompatible project image' >&2
    exit 1
fi
grep -Fq 'image 0.0.0 (scbolt:0.0.0)' "${tmpdir}/project-image.out"
test ! -e "${container_log}"

printf '%s\n' 'SCBOLT_IMAGE = scbolt:0.0.0' \
    > "${docker_test_config}/scbolt/config.mk"
if run_docker_config > "${tmpdir}/installed-image.out" 2>&1; then
    printf '%s\n' 'unexpectedly accepted incompatible installed image' >&2
    exit 1
fi
grep -Fq 'image 0.0.0 (scbolt:0.0.0)' "${tmpdir}/installed-image.out"
test ! -e "${container_log}"

# Check both upgrade and downgrade mismatches against an isolated runtime.
scbolt_command="${installed_root}/bin/scbolt"
for launcher_version in 1.0.0 1.0.1; do
    printf '%s\n' "${launcher_version}" > "${installed_root}/VERSION"
    for image_version in 1.0.0 1.0.1; do
        rm -f "${container_log}"
        if [ "${launcher_version}" = "${image_version}" ]; then
            run_docker_config --container-image="scbolt:${image_version}"
            grep -Fxq -- 'sha256:test' "${container_log}"
        else
            if run_docker_config --container-image="scbolt:${image_version}" \
                    > "${tmpdir}/changed-version.out" 2>&1; then
                printf 'unexpectedly accepted scBOLT %s with image %s\n' \
                    "${launcher_version}" "${image_version}" >&2
                exit 1
            fi
            grep -Fq "Docker image version mismatch: scBOLT ${launcher_version}, image ${image_version}" \
                "${tmpdir}/changed-version.out"
            test ! -e "${container_log}"
        fi
    done
done

# A missing launcher version cannot establish image compatibility.
for launcher_version in '' unknown; do
    printf '%s\n' "${launcher_version}" > "${installed_root}/VERSION"
    rm -f "${container_log}"
    if run_docker_config > "${tmpdir}/unknown-version.out" 2>&1; then
        printf '%s\n' 'unexpectedly accepted an unknown launcher version' >&2
        exit 1
    fi
    grep -Fq 'Cannot use Docker without a known scBOLT version' \
        "${tmpdir}/unknown-version.out"
    test ! -e "${container_log}"
done

# Installation validates the image before recording the Docker backend.
mkdir -p "${tmpdir}/fakebin"
ln -s "${fake_engine}" "${tmpdir}/fakebin/docker"
install_case=0
for image_version in "${scbolt_version}" 0.0.0 ''; do
    install_case=$((install_case + 1))
    install_home="${tmpdir}/image-install/${install_case}/home"
    install_config="${tmpdir}/image-install/${install_case}/config"
    mkdir -p "${install_home}" "${install_config}"
    if PATH="${tmpdir}/fakebin:${PATH}" \
        HOME="${install_home}" XDG_CONFIG_HOME="${install_config}" \
        SCBOLT_TEST_IMAGE_VERSION="${image_version}" \
            "${repo_root}/install" --backend=docker --env=core \
            > "${tmpdir}/image-install.out" 2>&1; then
        test "${image_version}" = "${scbolt_version}"
        grep -Fxq 'BACKEND = docker' "${install_config}/scbolt/config.mk"
    else
        test "${image_version}" != "${scbolt_version}"
        grep -Fq 'Docker image version mismatch' "${tmpdir}/image-install.out"
        test ! -e "${install_config}/scbolt/config.mk"
    fi
done

printf '%s\n' 'installation and Docker version compatibility tests passed'
