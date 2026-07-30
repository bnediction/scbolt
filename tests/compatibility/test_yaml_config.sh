#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
scbolt="${repo_root}/bin/scbolt"
legacy="${repo_root}/tests/fixtures/params.mk"
yaml="${repo_root}/tests/fixtures/scbolt.yml"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

"${scbolt}" config --raw --params="${legacy}" \
    | sed '/^PARAMS=/d' > "${tmpdir}/legacy.config"
"${scbolt}" config --raw --config="${yaml}" \
    | sed '/^PARAMS=/d' > "${tmpdir}/yaml.config"
diff -u "${tmpdir}/legacy.config" "${tmpdir}/yaml.config"

"${scbolt}" dry-run knnsc --params="${legacy}" \
    | sed -E 's#/tmp/scbolt-[A-Za-z0-9]+#/tmp/scbolt-TMP#g' \
    > "${tmpdir}/legacy.dry-run"
"${scbolt}" dry-run knnsc --config="${yaml}" \
    | sed -E 's#/tmp/scbolt-[A-Za-z0-9]+#/tmp/scbolt-TMP#g' \
    > "${tmpdir}/yaml.dry-run"
diff -u "${tmpdir}/legacy.dry-run" "${tmpdir}/yaml.dry-run"

"${scbolt}" config --raw --config="${yaml}" --neighbors=14 \
    > "${tmpdir}/override.config"
grep -qx 'NEIGHBORS=14' "${tmpdir}/override.config"

printf '%s\n' "YAML configuration compatibility tests passed"
