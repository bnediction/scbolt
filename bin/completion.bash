# shellcheck shell=bash

_scbolt_modules="load-genome load-fastq load-signatures load-cc load-go load-dorothea
alignment cellranger star qc velocyto
filtering normalization clustering dea scoring goea annotation
velocity potency
cotan cellrank stream knnbs macrostates
bin-cells bin-macrostates bin-dea bin-consensus binarization
spec max-nodes-soft max-consts-soft max-nodes-relaxed max-nodes-seed max-nodes-lock
bn-min bn-submin bn-diverse"

_scbolt_commands="init help show-config progress check dry-run clean ${_scbolt_modules}"
_scbolt_boolean_options="--logging= --spec-only-hvg= --pca-only-hvg= --velocity-only-hvg=
--cotan-only-hvg= --extend-epg= --prune-epg= --collapse-parameter=
--bin-scboolseq-only-hvg= --zeroes-are-zeroes= --bin-dea-only-hvg=
--canonic-filter= --canonic-infer= --min-self-loop-consts= --min-self-loop-infer=
--norm-mad= --cc-correction="
_scbolt_file_options="--params= --star-whitelist= --binarization-file= --macrostate-file=
--prior-knowledge= --spec-file="

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
}

_scbolt_complete_files() {
    local prefix="$1"
    local current="$2"
    local item

    COMPREPLY=()
    while IFS= read -r item; do
        COMPREPLY+=("${prefix}${item}")
    done < <(compgen -f -- "${current}")
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

    printf '%s\n' --params= --references= --reset-target= --trust-target= --logging= --help
    _scbolt_help_parameters "${target}"
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
        check|dry-run|show-config)
            for ((i = 1; i < COMP_CWORD; i++)); do
                word="${COMP_WORDS[i]}"
                case "${word}" in
                    "${command}")
                        ;;
                    --params|--references|--reset-target|--trust-target|--logging|--target)
                        ((i++))
                        ;;
                    --params=*|--references=*|--reset-target=*|--trust-target=*|--logging=*|--target=*)
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
            --params|--references|--reset-target|--trust-target|--logging|--target)
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

    case "${cur}" in
        --params=*)
            _scbolt_complete_files "--params=" "${cur#--params=}"
            return 0
            ;;
        --logging=*)
            _scbolt_complete_prefixed_words "--logging=" "true false" "${cur#--logging=}"
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
            ;;
    esac

    case "${prev}" in
        --params)
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
            _scbolt_complete_words "unique integrated" "${cur}"
            return 0
            ;;
    esac

    command="$(_scbolt_first_command || true)"
    target="$(_scbolt_target_from_args "${command}" || true)"

    if [ -z "${command}" ]; then
        _scbolt_complete_words "${_scbolt_commands}" "${cur}"
        return 0
    fi

    case "${command}" in
        init)
            if [[ "${cur}" == --* ]]; then
                _scbolt_complete_words "--remove --show --help -h" "${cur}"
            else
                _scbolt_complete_files "" "${cur}"
            fi
            ;;
        clean)
            if [[ "${cur}" == --* ]]; then
                _scbolt_complete_words "--all --stale --force --params= --references= --help -h" \
                    "${cur}"
            else
                _scbolt_complete_words "${_scbolt_modules}" "${cur}"
            fi
            ;;
        progress)
            if [[ "${cur}" == --* ]]; then
                _scbolt_complete_words "--all --params= --references= --help -h" "${cur}"
            else
                _scbolt_complete_words "${_scbolt_modules}" "${cur}"
            fi
            ;;
        show-config)
            if [[ "${cur}" == --* ]]; then
                if [ -n "${target}" ]; then
                    _scbolt_complete_words \
                        "--raw $(_scbolt_module_options "${target}") -h" "${cur}"
                else
                    _scbolt_complete_words \
                        "--raw --params= --references= --reset-target= --trust-target= --help -h" \
                        "${cur}"
                fi
            else
                _scbolt_complete_words "${_scbolt_modules}" "${cur}"
            fi
            ;;
        check|dry-run)
            if [[ "${cur}" == --* ]]; then
                if [ -n "${target}" ]; then
                    _scbolt_complete_words "$(_scbolt_module_options "${target}") -h" "${cur}"
                else
                    _scbolt_complete_words \
                        "--params= --references= --reset-target= --trust-target= --help -h" \
                        "${cur}"
                fi
            else
                _scbolt_complete_words "${_scbolt_modules}" "${cur}"
            fi
            ;;
        *)
            if [[ "${cur}" == --* ]]; then
                if [ -n "${target}" ]; then
                    _scbolt_complete_words "$(_scbolt_module_options "${target}") -h" "${cur}"
                else
                    _scbolt_complete_words \
                        "--params= --references= --reset-target= --trust-target= --logging= --help -h" \
                        "${cur}"
                fi
            fi
            ;;
    esac
}

complete -o bashdefault -o default -F _scbolt scbolt
