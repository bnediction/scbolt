# shellcheck shell=bash

_scbolt_modules="load-genome load-fastq load-matrix load-signatures load-cc load-go
alignment cellranger star qc velocyto
filtering normalization clustering dea scoring goea annotation
velocity potency
cotan cellrank stream knnsc macrostates
bin-cells bin-macrostates bin-dea bin-consensus binarization
spec max-nodes-soft max-consts-soft max-nodes-relaxed max-nodes-seed max-nodes-lock
bn-min bn-submin bn-diverse"

_scbolt_utilities="init version help config progress check diagnostics dry-run clean install"
_scbolt_commands="${_scbolt_utilities} ${_scbolt_modules}"
_scbolt_file_options="--config= --params= --old-file= --project-dir= --resources-dir= --star-whitelist=
--binarization-file= --count-file= --macrostate-file= --prior-knowledge= --spec-file="

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

_scbolt_complete_config_files() {
    local prefix="$1"
    local current="$2"
    local item

    COMPREPLY=()
    while IFS= read -r item; do
        if [ -d "${item}" ]; then
            COMPREPLY+=("${prefix}${item}/")
        elif [[ "${item}" == *.yml || "${item}" == *.yaml || "${item}" == *.mk ]]; then
            COMPREPLY+=("${prefix}${item}")
        fi
    done < <(compgen -f -- "${current}")

    if [[ "scbolt.yml" == "${current}"* ]] && [ ! -e "scbolt.yml" ]; then
        COMPREPLY+=("${prefix}scbolt.yml")
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

    option="$(printf '%s\n' "${parameter}" | tr '[:upper:]_.' '[:lower:]--')"
    printf -- '--%s=\n' "${option}"
}

_scbolt_config_args() {
    local i
    local word

    for ((i = 1; i < COMP_CWORD; i++)); do
        word="${COMP_WORDS[i]}"
        case "${word}" in
            --config=*|--params=*)
                printf '%s\n' "${word}"
                ;;
            --config|--params)
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
    local config_args=()
    local conditions
    local references

    mapfile -t config_args < <(_scbolt_config_args)
    conditions="$(
        command scbolt config --raw "${config_args[@]}" 2> /dev/null \
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
    local config_args=()

    mapfile -t config_args < <(_scbolt_config_args)

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
        if [[ "${parameter}" =~ ^([A-Z][A-Z0-9_]*|[a-z][a-z0-9_.-]*)$ ]]; then
            _scbolt_parameter_to_option "${parameter}"
        fi
    done < <(command scbolt "${target}" help "${config_args[@]}" 2> /dev/null)
}

_scbolt_module_options() {
    local target="$1"

    printf '%s\n' --config= --references= --reset-target= --trust-target= --trust-existing --old-file= \
        --project-dir= --resources-dir= --memory= --jobs= --seed= --representation= --label-column= \
        --backend= --logging= --help help
    _scbolt_help_parameters "${target}"
}

_scbolt_run_options() {
    printf '%s\n' --config= --references= --reset-target= --trust-target= --trust-existing --old-file= \
        --project-dir= --resources-dir= --memory= --jobs= --seed= --representation= --label-column= \
        --backend= --logging= --help
}

_scbolt_diagnostic_options() {
    printf '%s\n' --config= --references= --reset-target= --trust-target= --trust-existing --old-file= \
        --resources-dir= --backend= --help
}

_scbolt_progress_options() {
    printf '%s\n' --all --config= --resources-dir= --references= --trust-existing --old-file= --backend= --help
}

_scbolt_clean_options() {
    printf '%s\n' --all --stale --force --config= --resources-dir= --references= \
        --old-file= --backend= --help
}

_scbolt_config_options() {
    printf '%s\n' --default --raw "$(_scbolt_diagnostic_options)"
}

_scbolt_diagnostics_options() {
    printf '%s\n' --config= --backend= --help
}

_scbolt_install_options() {
    printf '%s\n' --all --completions --env= --backend= --help
}

_scbolt_init_selection_options() {
    printf '%s\n' --show --remove --config= --help
}

_scbolt_init_parameter_options() {
    printf '%s\n' --conditions= --organism= --labels= --spec-file= --count-file= \
        --macrostate-file= --binarization-file= --project-dir= --resources-dir= \
        --references= --backend= --logging= --jobs= --memory= --seed= --representation= --label-column=
}

_scbolt_complete_init_selection() {
    local current="$1"
    local item

    COMPREPLY=()
    while IFS= read -r item; do
        COMPREPLY+=("${item}")
    done < <(_scbolt_complete_config_files "" "${current}"; printf '%s\n' "${COMPREPLY[@]}")

    for item in $(_scbolt_init_selection_options); do
        if [[ "${item}" == "${current}"* ]]; then
            COMPREPLY+=("${item}")
        fi
    done

    _scbolt_keep_assignment_open
    _scbolt_keep_directory_open
}

_scbolt_init_has_config_file() {
    local i
    local word

    for ((i = 1; i < COMP_CWORD; i++)); do
        word="${COMP_WORDS[i]}"
        case "${word}" in
            init)
                ;;
            --config|--params)
                if [ "$((i + 1))" -lt "${COMP_CWORD}" ]; then
                    return 0
                fi
                ;;
            --config=*|--params=*)
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
                    --config|--params|--project-dir|--resources-dir|--references|--reset-target|--trust-target|--old-file|--logging|--target|--backend)
                        ((i++))
                        ;;
                    --config=*|--params=*|--project-dir=*|--resources-dir=*|--references=*|--reset-target=*|--trust-target=*|--old-file=*|--logging=*|--target=*|--backend=*)
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
            --config|--params|--project-dir|--resources-dir|--references|--reset-target|--trust-target|--old-file|--logging|--target|--backend)
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

_scbolt_option_values() {
    case "$1" in
        --backend=)
            printf '%s\n' "conda mamba micromamba docker"
            ;;
        --env=)
            printf '%s\n' "system align bonesis cellrank core cotan fastq potency scboolseq stream velocity velocyto"
            ;;
        --alignment-tool=)
            printf '%s\n' "cellranger star"
            ;;
        --omics-hvg-method=|--bin-hvg-method=)
            printf '%s\n' "loess binning"
            ;;
        --binarization-correction=|--correction=)
            printf '%s\n' "benjamini-hochberg bonferroni"
            ;;
        --binarization-method=)
            printf '%s\n' "scboolseq dea consensus"
            ;;
        --cellrank-method=)
            printf '%s\n' "stability top_n eigengap eigengap_coarse"
            ;;
        --clingo-config-*=)
            printf '%s\n' "auto frumpy jumpy tweety handy crafty trendy many"
            ;;
        --clingo-mode-*=)
            printf '%s\n' "opt optN ignore"
            ;;
        --clingo-strategy-*=)
            printf '%s\n' "bb bb,lin bb,hier bb,inc bb,dec usc usc,oll usc,one usc,k usc,pmres"
            ;;
        --cotan-method=)
            printf '%s\n' "classic soft-merging strong-merging"
            ;;
        --dea-method=)
            printf '%s\n' "wilcoxon welch welch_overestimate"
            ;;
        --dorothea-api=)
            printf '%s\n' "modern legacy"
            ;;
        --geneinfo-version=|--hcop-version=)
            printf '%s\n' "bundled latest file"
            ;;
        --integration=)
            printf '%s\n' "bbknn scanorama ingest"
            ;;
        --macrostate-method=)
            printf '%s\n' "knnsc stream cellrank cotan"
            ;;
        --omnipath-version=)
            printf '%s\n' "latest YYYY-MM-DD"
            ;;
        --organism=)
            printf '%s\n' "mouse human"
            ;;
        --prior-knowledge=)
            printf '%s\n' "dorothea collectri"
            ;;
        --scbolt-container-engine=)
            printf '%s\n' "docker podman"
            ;;
        --star-barcode-filter=)
            printf '%s\n' "auto threshold top"
            ;;
        --stream-clustering-method=)
            printf '%s\n' "kmeans ap sc"
            ;;
        --stream-extend-mode=)
            printf '%s\n' "QuantDists QuantCentroid WeigthedCentroid"
            ;;
        --velocity-mode=)
            printf '%s\n' "deterministic stochastic dynamical"
            ;;
        --logging=|--binarization-dea-only-hvg=|--cell-cycle-correction=|\
        --centered-pca=|--consistent-mad=|--cotan-only-hvg=|\
        --dorothea-compatibility=|--pca-only-hvg=|--scboolseq-only-hvg=|\
        --stream-collapse-parameter=|--stream-extend=|--stream-prune=|\
        --velocity-only-hvg=|--zeroes-are-zeroes=|\
        --clause-continuation-*=|--domain-continuation-*=|\
        --minimize-self-loops-*=)
            printf '%s\n' "true false"
            ;;
    esac
}

_scbolt_complete_choice_files() {
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
    while IFS= read -r item; do
        if [ -d "${item}" ]; then
            COMPREPLY+=("${prefix}${item}/")
        else
            COMPREPLY+=("${prefix}${item}")
        fi
    done < <(compgen -f -- "${current}")
    _scbolt_keep_assignment_open
    _scbolt_keep_directory_open
}

_scbolt_complete_option_value() {
    local option="$1"
    local current="$2"
    local prefix="$3"
    local choices

    choices="$(_scbolt_option_values "${option}")"
    case "${option}" in
        --config=|--params=)
            _scbolt_complete_config_files "${prefix}" "${current}"
            return 0
            ;;
        --prior-knowledge=)
            _scbolt_complete_choice_files "${prefix}" "${choices}" "${current}"
            return 0
            ;;
    esac
    if [ -n "${choices}" ]; then
        _scbolt_complete_prefixed_words "${prefix}" "${choices}" "${current}"
        return 0
    fi
    case " ${_scbolt_file_options} " in
        *" ${option} "*)
            _scbolt_complete_files "${prefix}" "${current}"
            return 0
            ;;
    esac
    case "${option}" in
        --count-file-*=|--macrostate-file-*=)
            _scbolt_complete_files "${prefix}" "${current}"
            return 0
            ;;
    esac
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
        --config=*|--params=*)
            option="${cur%%=*}="
            _scbolt_complete_config_files "${option}" "${cur#*=}"
            return 0
            ;;
        --old-file=*)
            _scbolt_complete_files "--old-file=" "${cur#--old-file=}"
            return 0
            ;;
        --resources-dir=*)
            _scbolt_complete_files "--resources-dir=" "${cur#--resources-dir=}"
            return 0
            ;;
        --project-dir=*)
            _scbolt_complete_files "--project-dir=" "${cur#--project-dir=}"
            return 0
            ;;
        --logging=*)
            _scbolt_complete_prefixed_words "--logging=" "true false" "${cur#--logging=}"
            return 0
            ;;
        --backend=*)
            _scbolt_complete_prefixed_words "--backend=" "conda mamba micromamba docker" "${cur#--backend=}"
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
            if _scbolt_complete_option_value "${option}" "${cur#*=}" "${option}"; then
                return 0
            fi
            _scbolt_no_completion
            return 0
            ;;
    esac

    if [ "${prev}" = "=" ] && [ "${COMP_CWORD}" -ge 2 ]; then
        assignment_option="${COMP_WORDS[COMP_CWORD - 2]}"
        case "${assignment_option}" in
            --reset-target|--trust-target|--target)
                _scbolt_complete_words "${_scbolt_modules}" "${cur}"
                return 0
                ;;
            --references)
                _scbolt_complete_words "$(_scbolt_references)" "${cur}"
                return 0
                ;;
        esac
        option="${assignment_option}="
        if _scbolt_complete_option_value "${option}" "${cur}" ""; then
            return 0
        fi
        _scbolt_no_completion
        return 0
    fi

    case "${prev}" in
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
    if [[ "${prev}" == --* ]]; then
        option="${prev%=}="
        if _scbolt_complete_option_value "${option}" "${cur}" ""; then
            return 0
        fi
    fi

    target="$(_scbolt_target_from_args "${command}" || true)"

    if [ -z "${command}" ]; then
        if [ -z "${cur}" ]; then
            _scbolt_complete_words "${_scbolt_modules}" "${cur}"
        else
            _scbolt_complete_words "${_scbolt_commands}" "${cur}"
        fi
        return 0
    fi

    case "${command}" in
        init)
            if [[ "${cur}" == --* ]]; then
                if _scbolt_init_has_config_file; then
                    _scbolt_complete_words "$(_scbolt_init_parameter_options)" "${cur}"
                else
                    _scbolt_complete_words "$(_scbolt_init_selection_options)" "${cur}"
                fi
            elif _scbolt_init_has_config_file; then
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
                    _scbolt_complete_words "--default --raw $(_scbolt_module_options "${target}")" \
                        "${cur}"
                else
                    _scbolt_complete_words "$(_scbolt_config_options)" "${cur}"
                fi
            else
                if [ -n "${target}" ]; then
                    _scbolt_complete_words "--default --raw $(_scbolt_module_options "${target}")" \
                        "${cur}"
                else
                    _scbolt_complete_words "${_scbolt_modules} $(_scbolt_config_options)" "${cur}"
                fi
            fi
            ;;
        diagnostics)
            _scbolt_complete_words "$(_scbolt_diagnostics_options)" "${cur}"
            ;;
        install)
            if [[ "${cur}" == --* ]]; then
                _scbolt_complete_words "$(_scbolt_install_options)" "${cur}"
            else
                _scbolt_complete_words "conda mamba micromamba docker $(_scbolt_install_options)" "${cur}"
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
