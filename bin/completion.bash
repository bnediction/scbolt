# shellcheck shell=bash
_scbolt_go_complete() {
    local reply
    COMPREPLY=()
    while IFS= read -r reply; do
        COMPREPLY+=("${reply}")
    done < <(command scbolt __complete --index "${COMP_CWORD}" -- "${COMP_WORDS[@]}")
    for reply in "${COMPREPLY[@]}"; do
        if [[ "${reply}" == *= || "${reply}" == */ ]]; then
            compopt -o nospace 2>/dev/null || true
            break
        fi
    done
}
complete -F _scbolt_go_complete scbolt
