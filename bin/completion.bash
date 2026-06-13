# shellcheck shell=bash

_scbolt_modules="load-genome load-fastq load-matrix load-signatures load-cc load-go
alignment cellranger star qc velocyto
filtering normalization clustering dea scoring goea annotation
velocity potency
cotan cellrank stream knnsc macrostates
bin-cells bin-macrostates bin-dea bin-consensus binarization
spec max-nodes-soft max-consts-soft max-nodes-relaxed max-nodes-seed max-nodes-lock
bn-min bn-submin bn-diverse"

_scbolt_commands="init help config progress check dry-run clean ${_scbolt_modules}"
_scbolt_boolean_options="--logging= --spec-only-hvg= --pca-only-hvg= --velocity-only-hvg=
--cotan-only-hvg= --extend-epg= --prune-epg= --collapse-parameter=
--bin-scboolseq-only-hvg= --zeroes-are-zeroes= --bin-dea-only-hvg=
--canonic-filter= --canonic-infer= --min-self-loop-consts= --min-self-loop-infer=
--norm-mad= --cc-correction= --dorothea-compatibility="
_scbolt_file_options="--params= --old-file= --results-dir= --public-dir= --star-whitelist=
--binarization-file= --macrostate-files= --prior-knowledge= --spec-file="

_scbolt_complete_words() {
    local choices="$1"
    local current="$2"
    local item

    COMPREPLY=()
    for item in ${choices}; do
        if [[ "${item}" == "${current}"* ]]; then
            COMPREPLY+=("${item}")
        fi
    done

    _scbolt_keep_assignment_open
}

_scbolt_complete_prefixed_words() {
    local prefix="$1"
    local choices="$2"
    local current="$3"
    local item

    COMPREPLY=()
    for item in ${choices}; do
        if [[ "${item}" == "${current}"* ]]; then
            COMPREPLY+=("${prefix}${item}")
        fi
    done

    _scbolt_keep_assignment_open
}

_scbolt_complete_files() {
    local prefix="$1"
    local current="$2"
    local item

    COMPREPLY=()
    while IFS= read -r item; do
        if [ -d "${item}" ]; then
            COMPREPLY+=("${prefix}${item}/")
        else
            COMPREPLY+=("${prefix}${item}")
        fi
    done < <(compgen -f -- "${current}")

    _scbolt_keep_directory_open
}

_scbolt_complete_params_files() {
    local prefix="$1"
    local current="$2"
    local item

    COMPREPLY=()
    while IFS= read -r item; do
        if [ -d "${item}" ]; then
            COMPREPLY+=("${prefix}${item}/")
        elif [[ "${item}" == *.mk ]]; then
            COMPREPLY+=("${prefix}${item}")
        fi
    done < <(compgen -f -- "${current}")

    if [[ "params.mk" == "${current}"* ]] && [ ! -e "params.mk" ]; then
        COMPREPLY+=("${prefix}params.mk")
    fi

    _scbolt_keep_directory_open
}

_scbolt_keep_assignment_open() {
    local reply

    for reply in "${COMPREPLY[@]}"; do
        if [[ "${reply}" == *= ]]; then
            compopt -o nospace 2> /dev/null || true
            return 0
        fi
    done
}

_scbolt_keep_directory_open() {
    local reply

    for reply in "${COMPREPLY[@]}"; do
        if [[ "${reply}" == */ ]]; then
            compopt -o nospace 2> /dev/null || true
            return 0
        fi
    done
}

_scbolt_no_completion() {
    COMPREPLY=()
    compopt +o default +o bashdefault 2> /dev/null || true
}

_scbolt_is_module() {
    local value="$1"
    local module

    for module in ${_scbolt_modules}; do
        if [ "${module}" = "${value}" ]; then
            return 0
        fi
    done

    return 1
}

_scbolt_parameter_to_option() {
    local parameter="$1"
    local option

    option="$(printf '%s\n' "${parameter}" | tr '[:upper:]_' '[:lower:]-')"
    printf -- '--%s=\n' "${option}"
}

_scbolt_params_args() {
    local i
    local word

    for ((i = 1; i < COMP_CWORD; i++)); do
        word="${COMP_WORDS[i]}"
        case "${word}" in
            --params=*)
                printf '%s\n' "${word}"
                ;;
            --params)
                if [ "$((i + 1))" -lt "${COMP_CWORD}" ]; then
                    printf '%s\n' "${word}"
                    printf '%s\n' "${COMP_WORDS[i + 1]}"
                    ((i++))
                fi
                ;;
        esac
    done
}

_scbolt_references() {
    local params_args=()
    local conditions
    local references

    mapfile -t params_args < <(_scbolt_params_args)
    conditions="$(
        command scbolt config --raw "${params_args[@]}" 2> /dev/null \
            | awk -F= '$1 == "CONDITIONS" { print $2; exit }'
    )"

    if [ -n "${conditions}" ]; then
        references="${conditions}"
        if [ "$(wc -w <<< "${conditions}")" -gt 1 ]; then
            references="${references} integrated"
        fi
        printf '%s\n' "${references}"
    fi
}

_scbolt_help_parameters() {
    local target="$1"
    local in_parameters=false
    local line
    local parameter
    local params_args=()

    mapfile -t params_args < <(_scbolt_params_args)

    while IFS= read -r line; do
        case "${line}" in
            Parameters)
                in_parameters=true
                continue
                ;;
            Description|Targets|Dependencies|Project|Workflow|Methods|Execution)
                in_parameters=false
                ;;
        esac

        if [ "${in_parameters}" != "true" ]; then
            continue
        fi

        line="${line#"${line%%[![:space:]]*}"}"
        parameter="${line%%[[:space:]]*}"
        if [[ "${parameter}" =~ ^[A-Z][A-Z0-9_]*$ ]]; then
            _scbolt_parameter_to_option "${parameter}"
        fi
    done < <(command scbolt "${target}" help "${params_args[@]}" 2> /dev/null)
}

_scbolt_module_options() {
    local target="$1"

    printf '%s\n' --params= --references= --reset-target= --trust-target= --old-file= \
        --results-dir= --public-dir= --memory= --jobs= --seed= --use-rep= --label-col= \
        --logging= --help help
    _scbolt_help_parameters "${target}"
}

_scbolt_run_options() {
    printf '%s\n' --params= --references= --reset-target= --trust-target= --old-file= \
        --results-dir= --public-dir= --memory= --jobs= --seed= --use-rep= --label-col= \
        --logging= --help
}

_scbolt_diagnostic_options() {
    printf '%s\n' --params= --references= --reset-target= --trust-target= --old-file= \
        --public-dir= --help
}

_scbolt_progress_options() {
    printf '%s\n' --all --params= --public-dir= --references= --old-file= --help
}

_scbolt_clean_options() {
    printf '%s\n' --all --stale --force --params= --public-dir= --references= \
        --old-file= --help
}

_scbolt_init_selection_options() {
    printf '%s\n' --show --remove --help
}

_scbolt_init_parameter_options() {
    printf '%s\n' --conditions= --organism= --label= --spec-file= --count-files= \
        --macrostate-files= --binarization-file= --results-dir= --public-dir= \
        --references= --logging= --jobs= --memory= --seed= --use-rep= --label-col=
}

_scbolt_complete_init_selection() {
    local current="$1"
    local item

    COMPREPLY=()
    while IFS= read -r item; do
        COMPREPLY+=("${item}")
    done < <(_scbolt_complete_params_files "" "${current}"; printf '%s\n' "${COMPREPLY[@]}")

    for item in $(_scbolt_init_selection_options); do
        if [[ "${item}" == "${current}"* ]]; then
            COMPREPLY+=("${item}")
        fi
    done

    _scbolt_keep_assignment_open
    _scbolt_keep_directory_open
}

_scbolt_init_has_params_file() {
    local i
    local word

    for ((i = 1; i < COMP_CWORD; i++)); do
        word="${COMP_WORDS[i]}"
        case "${word}" in
            init)
                ;;
            --params)
                if [ "$((i + 1))" -lt "${COMP_CWORD}" ]; then
                    return 0
                fi
                ;;
            --params=*)
                return 0
                ;;
            --remove|--show|-h|--help|--*=*|*=*)
                ;;
            --*)
                ((i++))
                ;;
            *)
                return 0
                ;;
        esac
    done

    return 1
}

_scbolt_complete_multi_module_position() {
    local options="$1"
    local current="$2"

    if [ -z "${current}" ] || [[ "${current}" == -* ]]; then
        _scbolt_complete_words "${options}" "${current}"
    else
        _scbolt_complete_words "${_scbolt_modules}" "${current}"
    fi
}

_scbolt_target_from_args() {
    local command="$1"
    local i
    local word

    if _scbolt_is_module "${command}"; then
        printf '%s\n' "${command}"
        return 0
    fi

    case "${command}" in
        check|dry-run|config|progress|clean)
            for ((i = 1; i < COMP_CWORD; i++)); do
                word="${COMP_WORDS[i]}"
                case "${word}" in
                    "${command}")
                        ;;
                    --params|--public-dir|--references|--reset-target|--trust-target|--old-file|--logging|--target)
                        ((i++))
                        ;;
                    --params=*|--public-dir=*|--references=*|--reset-target=*|--trust-target=*|--old-file=*|--logging=*|--target=*)
                        ;;
                    --*|*=*)
                        ;;
                    *)
                        if _scbolt_is_module "${word}"; then
                            printf '%s\n' "${word}"
                            return 0
                        fi
                        ;;
                esac
            done
            ;;
    esac

    return 1
}

_scbolt_first_command() {
    local i
    local word

    for ((i = 1; i < COMP_CWORD; i++)); do
        word="${COMP_WORDS[i]}"
        case "${word}" in
            --params|--public-dir|--references|--reset-target|--trust-target|--old-file|--logging|--target)
                ((i++))
                ;;
            --*|*=*)
                ;;
            *)
                printf '%s\n' "${word}"
                return 0
                ;;
        esac
    done

    return 1
}

_scbolt() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD - 1]}"
    local command
    local target
    local option
    local assignment_option
    local line_before_cursor

    line_before_cursor="${COMP_LINE-}"
    line_before_cursor="${line_before_cursor:0:${COMP_POINT:-${#line_before_cursor}}}"

    if [[ "${line_before_cursor}" =~ (^|[[:space:]])--references=([^[:space:]]*)$ ]]; then
        if [[ "${cur}" == --references=* ]]; then
            _scbolt_complete_prefixed_words "--references=" "$(_scbolt_references)" \
                "${BASH_REMATCH[2]}"
        else
            _scbolt_complete_words "$(_scbolt_references)" "${BASH_REMATCH[2]}"
        fi
        return 0
    fi

    if [[ "${line_before_cursor}" =~ (^|[[:space:]])--reset-target=([^[:space:]]*)$ ]]; then
        if [[ "${cur}" == --reset-target=* ]]; then
            _scbolt_complete_prefixed_words "--reset-target=" "${_scbolt_modules}" \
                "${BASH_REMATCH[2]}"
        else
            _scbolt_complete_words "${_scbolt_modules}" "${BASH_REMATCH[2]}"
        fi
        return 0
    fi

    if [[ "${line_before_cursor}" =~ (^|[[:space:]])--trust-target=([^[:space:]]*)$ ]]; then
        if [[ "${cur}" == --trust-target=* ]]; then
            _scbolt_complete_prefixed_words "--trust-target=" "${_scbolt_modules}" \
                "${BASH_REMATCH[2]}"
        else
            _scbolt_complete_words "${_scbolt_modules}" "${BASH_REMATCH[2]}"
        fi
        return 0
    fi

    command="$(_scbolt_first_command || true)"

    case "${cur}" in
        --params=*)
            if [ "${command}" = "init" ]; then
                _scbolt_complete_params_files "--params=" "${cur#--params=}"
            else
                _scbolt_complete_files "--params=" "${cur#--params=}"
            fi
            return 0
            ;;
        --old-file=*)
            _scbolt_complete_files "--old-file=" "${cur#--old-file=}"
            return 0
            ;;
        --public-dir=*)
            _scbolt_complete_files "--public-dir=" "${cur#--public-dir=}"
            return 0
            ;;
        --logging=*)
            _scbolt_complete_prefixed_words "--logging=" "true false" "${cur#--logging=}"
            return 0
            ;;
        --references=*)
            _scbolt_complete_prefixed_words "--references=" "$(_scbolt_references)" \
                "${cur#--references=}"
            return 0
            ;;
        --reset-target=*)
            _scbolt_complete_prefixed_words "--reset-target=" "${_scbolt_modules}" \
                "${cur#--reset-target=}"
            return 0
            ;;
        --trust-target=*)
            _scbolt_complete_prefixed_words "--trust-target=" "${_scbolt_modules}" \
                "${cur#--trust-target=}"
            return 0
            ;;
        --target=*)
            _scbolt_complete_prefixed_words "--target=" "${_scbolt_modules}" "${cur#--target=}"
            return 0
            ;;
        --*=*)
            option="${cur%%=*}="
            case " ${_scbolt_boolean_options} " in
                *" ${option} "*)
                    _scbolt_complete_prefixed_words "${option}" "true false" "${cur#*=}"
                    return 0
                    ;;
            esac
            case " ${_scbolt_file_options} " in
                *" ${option} "*)
                    _scbolt_complete_files "${option}" "${cur#*=}"
                    return 0
                    ;;
            esac
            _scbolt_no_completion
            return 0
            ;;
    esac

    if [ "${prev}" = "=" ] && [ "${COMP_CWORD}" -ge 2 ]; then
        assignment_option="${COMP_WORDS[COMP_CWORD - 2]}"
        case "${assignment_option}" in
            --params)
                _scbolt_complete_files "" "${cur}"
                return 0
                ;;
            --old-file|--public-dir)
                _scbolt_complete_files "" "${cur}"
                return 0
                ;;
            --logging)
                _scbolt_complete_words "true false" "${cur}"
                return 0
                ;;
            --reset-target|--trust-target|--target)
                _scbolt_complete_words "${_scbolt_modules}" "${cur}"
                return 0
                ;;
            --references)
                _scbolt_complete_words "$(_scbolt_references)" "${cur}"
                return 0
                ;;
        esac
        _scbolt_no_completion
        return 0
    fi

    case "${prev}" in
        --params|--params=)
            if [ "${command}" = "init" ]; then
                _scbolt_complete_params_files "" "${cur}"
            else
                _scbolt_complete_files "" "${cur}"
            fi
            return 0
            ;;
        --old-file|--old-file=)
            _scbolt_complete_files "" "${cur}"
            return 0
            ;;
        --public-dir|--public-dir=)
            _scbolt_complete_files "" "${cur}"
            return 0
            ;;
        --logging|--logging=)
            _scbolt_complete_words "true false" "${cur}"
            return 0
            ;;
        --reset-target|--reset-target=|--trust-target|--trust-target=|--target|--target=)
            _scbolt_complete_words "${_scbolt_modules}" "${cur}"
            return 0
            ;;
        --references|--references=)
            _scbolt_complete_words "$(_scbolt_references)" "${cur}"
            return 0
            ;;
        --*=)
            _scbolt_no_completion
            return 0
            ;;
    esac

    target="$(_scbolt_target_from_args "${command}" || true)"

    if [ -z "${command}" ]; then
        _scbolt_complete_words "${_scbolt_commands}" "${cur}"
        return 0
    fi

    case "${command}" in
        init)
            if [[ "${cur}" == --* ]]; then
                if _scbolt_init_has_params_file; then
                    _scbolt_complete_words "$(_scbolt_init_parameter_options)" "${cur}"
                else
                    _scbolt_complete_words "$(_scbolt_init_selection_options)" "${cur}"
                fi
            elif _scbolt_init_has_params_file; then
                _scbolt_complete_words "$(_scbolt_init_parameter_options)" "${cur}"
            else
                _scbolt_complete_init_selection "${cur}"
            fi
            ;;
        clean)
            if [[ "${cur}" == --* ]]; then
                _scbolt_complete_words "$(_scbolt_clean_options)" "${cur}"
            else
                if [ -n "${target}" ]; then
                    _scbolt_complete_multi_module_position "$(_scbolt_clean_options)" "${cur}"
                else
                    _scbolt_complete_words "${_scbolt_modules} $(_scbolt_clean_options)" "${cur}"
                fi
            fi
            ;;
        progress)
            if [[ "${cur}" == --* ]]; then
                if [ -n "${target}" ]; then
                    _scbolt_complete_words "$(_scbolt_progress_options) $(_scbolt_help_parameters "${target}")" \
                        "${cur}"
                else
                    _scbolt_complete_words "$(_scbolt_progress_options)" "${cur}"
                fi
            else
                if [ -n "${target}" ]; then
                    _scbolt_complete_multi_module_position \
                        "$(_scbolt_progress_options) $(_scbolt_help_parameters "${target}")" \
                        "${cur}"
                else
                    _scbolt_complete_words \
                        "${_scbolt_modules} $(_scbolt_progress_options)" \
                        "${cur}"
                fi
            fi
            ;;
        config)
            if [[ "${cur}" == --* ]]; then
                if [ -n "${target}" ]; then
                    _scbolt_complete_words "--raw $(_scbolt_module_options "${target}")" \
                        "${cur}"
                else
                    _scbolt_complete_words "--raw $(_scbolt_diagnostic_options)" "${cur}"
                fi
            else
                if [ -n "${target}" ]; then
                    _scbolt_complete_words "--raw $(_scbolt_module_options "${target}")" \
                        "${cur}"
                else
                    _scbolt_complete_words "${_scbolt_modules} --raw $(_scbolt_diagnostic_options)" "${cur}"
                fi
            fi
            ;;
        check|dry-run)
            if [[ "${cur}" == --* ]]; then
                if [ -n "${target}" ]; then
                    _scbolt_complete_words "$(_scbolt_module_options "${target}")" "${cur}"
                else
                    _scbolt_complete_words "$(_scbolt_diagnostic_options)" "${cur}"
                fi
            else
                if [ -n "${target}" ]; then
                    _scbolt_complete_words "$(_scbolt_module_options "${target}")" "${cur}"
                else
                    _scbolt_complete_words "${_scbolt_modules} $(_scbolt_diagnostic_options)" "${cur}"
                fi
            fi
            ;;
        *)
            if [[ "${cur}" == --* ]]; then
                if [ -n "${target}" ]; then
                    _scbolt_complete_words "$(_scbolt_module_options "${target}")" "${cur}"
                else
                    _scbolt_complete_words "$(_scbolt_run_options)" "${cur}"
                fi
            else
                if [ -n "${target}" ]; then
                    _scbolt_complete_multi_module_position "$(_scbolt_module_options "${target}")" "${cur}"
                else
                    _scbolt_complete_words "$(_scbolt_run_options)" "${cur}"
                fi
            fi
            ;;
    esac
}

if ! complete -o nosort -o bashdefault -o default -F _scbolt scbolt 2> /dev/null; then
    complete -o bashdefault -o default -F _scbolt scbolt
fi
