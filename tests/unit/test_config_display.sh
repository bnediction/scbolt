#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
params="tests/fixtures/params.mk"

render_config() {
    make -s -C "${repo_root}" config \
        PARAMS="${params}" TARGET=bin-consensus \
        BIN_INCLUDE_NODES="$1"
}

short_list="$(render_config 'A B C D')"
grep -Eq '^bin include nodes +: A B C D$' <<< "${short_list}"

long_list="$(render_config 'A B C D E F G')"
grep -Eq '^bin include nodes +: A B C D \.\.\. \(3 more\)$' \
    <<< "${long_list}"
if grep -Eq '^bin include nodes +: .* E( |$)' <<< "${long_list}"; then
    printf '%s\n' "config summary exposes hidden list values" >&2
    exit 1
fi

raw_config="$(
    make -s -C "${repo_root}" config \
        PARAMS="${params}" CONFIG_RAW=true \
        BIN_INCLUDE_NODES='A B C D E F G'
)"
grep -qFx 'BIN_INCLUDE_NODES=A B C D E F G' <<< "${raw_config}"

printf '%s\n' "Config display tests passed"
