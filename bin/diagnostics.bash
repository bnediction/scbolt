# shellcheck shell=bash

diagnostics_help() {
    cat <<'EOF'
usage: scbolt diagnostics

Report diagnostics for the scBOLT installation, host platform, selected
runtime backend, and numerical reproducibility profile.

This command does not validate pipeline inputs or module-specific
requirements. Use 'scbolt <command> check' for module validation.
EOF
}

diagnostic_sections=()
diagnostic_names=()
diagnostic_values=()
diagnostic_statuses=()
diagnostic_details=()

diagnostic_add() {
    diagnostic_sections+=("$1")
    diagnostic_statuses+=("$2")
    diagnostic_names+=("$3")
    diagnostic_values+=("$4")
    diagnostic_details+=("${5:-}")
}

diagnostic_resolve_path() {
    local path="$1"
    local base="${2:-${PWD}}"
    local resolved

    if [[ "${path}" = /* ]]; then
        resolved="${path}"
    else
        resolved="${base%/}/${path}"
    fi
    if command -v realpath >/dev/null 2>&1; then
        realpath -m "${resolved}" 2>/dev/null || printf '%s\n' "${resolved}"
    else
        printf '%s\n' "${resolved}"
    fi
}

diagnostic_project_value() {
    local path="$1"
    local variable="$2"
    local default_value="${3:-}"
    local value

    if [ -n "${path}" ] && [ -f "${path}" ]; then
        value="$(read_project_variable "${path}" "${variable}" 2>/dev/null || true)"
        if [ -n "${value}" ]; then
            printf '%s\n' "${value}"
            return 0
        fi
    fi
    value="$(read_config_variable "${SCBOLT_USER_CONFIG}" "${variable}" 2>/dev/null || true)"
    if [ -n "${value}" ]; then
        printf '%s\n' "${value}"
        return 0
    fi
    value="$(read_config_variable "${SCBOLT_DEFAULT_PARAMS}" "${variable}" 2>/dev/null || true)"
    if [ -n "${value}" ]; then
        printf '%s\n' "${value}"
    else
        printf '%s\n' "${default_value}"
    fi
}

diagnostic_project_source() {
    local path="$1"
    local variable="$2"

    if [ -n "${path}" ] && [ -f "${path}" ] \
            && [ -n "$(read_project_variable "${path}" "${variable}" 2>/dev/null || true)" ]; then
        printf '%s\n' "project configuration"
    elif [ -n "$(read_config_variable "${SCBOLT_USER_CONFIG}" "${variable}" 2>/dev/null || true)" ]; then
        printf '%s\n' "global configuration"
    else
        printf '%s\n' "default"
    fi
}

diagnostic_version_number() {
    local command="$1"
    local output
    shift

    output="$("${command}" "$@" 2>/dev/null || true)"
    output="${output%%$'\n'*}"
    sed -E 's/^[^0-9]*([0-9]+([.][0-9]+)*).*$/\1/' <<< "${output}"
}

diagnostic_version_at_least() {
    local actual="$1"
    local required="$2"
    local first

    first="$(printf '%s\n%s\n' "${required}" "${actual}" | sort -V | sed -n '1p')"
    [ "${first}" = "${required}" ]
}

diagnostic_cpu_field() {
    local name="$1"

    if [ -r /proc/cpuinfo ]; then
        awk -F: -v name="${name}" '$1 ~ "^[[:space:]]*" name "[[:space:]]*$" {
            sub(/^[[:space:]]*/, "", $2); print $2; exit
        }' /proc/cpuinfo
    fi
}

diagnostic_cpu_model() {
    local value

    value="$(diagnostic_cpu_field 'model name')"
    if [ -z "${value}" ] && command -v sysctl >/dev/null 2>&1; then
        value="$(sysctl -n machdep.cpu.brand_string 2>/dev/null || true)"
    fi
    if [ -z "${value}" ]; then
        value="${PROCESSOR_IDENTIFIER:-}"
    fi
    printf '%s\n' "${value}"
}

diagnostic_microarchitecture() {
    local processor="$1"
    local vendor
    local family
    local model
    local lower="${processor,,}"

    vendor="$(diagnostic_cpu_field vendor_id)"
    family="$(diagnostic_cpu_field 'cpu family')"
    model="$(diagnostic_cpu_field model)"
    case "${lower}" in
        *"meteor lake"*) printf '%s\n' "Meteor Lake"; return ;;
        *ultra*125*|*ultra*135*|*ultra*155*|*ultra*165*|*ultra*185*)
            printf '%s\n' "Meteor Lake"; return ;;
        *"zen 3"*|*zen3*|*znver3*) printf '%s\n' "AMD Zen 3"; return ;;
        *"emerald rapids"*) printf '%s\n' "Emerald Rapids"; return ;;
        *haswell*) printf '%s\n' "Haswell"; return ;;
        *"apple m"*) printf '%s\n' "Apple Silicon"; return ;;
    esac
    if [ "${vendor}" = "AuthenticAMD" ] && [ "${family}" = "25" ]; then
        case "${model}" in
            [0-9]|1[0-5]|3[2-9]|4[0-9]|5[0-9]|6[4-9]|7[0-9]|8[0-9]|9[0-5])
                printf '%s\n' "AMD Zen 3"
                ;;
        esac
    fi
}

diagnostic_haswell_compatible() {
    local architecture="$1"
    local flags

    case "${architecture}" in
        x86_64|amd64) ;;
        *) return 1 ;;
    esac
    flags="$(diagnostic_cpu_field flags)"
    [[ " ${flags} " == *" avx2 "* && " ${flags} " == *" fma "* ]]
}

diagnostic_environment_exists() {
    local manager="$1"
    local environment="$2"
    local environments

    environments="$("${manager}" env list 2>/dev/null || true)"
    awk -v environment="${environment}" '
        $NF == environment || $NF ~ ("/" environment "$") { found = 1 }
        END { exit !found }
    ' <<< "${environments}"
}

diagnostic_collect_scbolt() {
    local configuration="$1"
    local configuration_path="$2"
    local configuration_base="$3"
    local project_dir="$4"
    local resources_dir="$5"
    local configuration_issue="$6"
    local executable
    local version="unknown"

    [ -f "${SCBOLT_VERSION_FILE}" ] && IFS= read -r version < "${SCBOLT_VERSION_FILE}"
    executable="$(command -v scbolt 2>/dev/null || printf '%s' "${SCBOLT_SCRIPT}")"
    diagnostic_add scBOLT ok version "${version}"
    diagnostic_add scBOLT ok executable "${executable}"
    if [ -n "${configuration_issue}" ]; then
        diagnostic_add scBOLT error "configuration file" "${configuration_path:-invalid}" \
            "${configuration_issue}"
    elif [ -n "${configuration}" ]; then
        diagnostic_add scBOLT ok "configuration file" "${configuration_path}"
    else
        diagnostic_add scBOLT warning "configuration file" "not selected" \
            "No active project is required for installation diagnostics."
    fi
    diagnostic_add scBOLT ok "project directory" \
        "$(diagnostic_resolve_path "${project_dir}" "${configuration_base}")"
    diagnostic_add scBOLT ok "resources directory" \
        "$(diagnostic_resolve_path "${resources_dir}" "${configuration_base}")"
}

diagnostic_collect_host() {
    local operating_system
    local architecture
    local processor
    local microarchitecture

    operating_system="$(uname -s 2>/dev/null || printf unknown)"
    architecture="$(uname -m 2>/dev/null || printf unknown)"
    processor="$(diagnostic_cpu_model)"
    microarchitecture="$(diagnostic_microarchitecture "${processor}")"
    diagnostic_add Host ok "operating system" "${operating_system}"
    diagnostic_add Host ok architecture "${architecture}"
    if [ -n "${processor}" ]; then
        diagnostic_add Host ok processor "${processor}"
    else
        diagnostic_add Host warning processor unknown \
            "The exact processor model could not be detected."
    fi
    case "${microarchitecture}" in
        "Meteor Lake")
            diagnostic_add Host ok "CPU microarchitecture" "${microarchitecture}" \
                "Canonical reference processor profile."
            ;;
        "AMD Zen 3")
            diagnostic_add Host ok "CPU microarchitecture" "${microarchitecture}" \
                "Strict numerical profile validated against the canonical references."
            ;;
        "")
            diagnostic_add Host warning "CPU microarchitecture" unknown \
                "Exact numerical identity cannot be inferred from this host report."
            ;;
        *)
            diagnostic_add Host warning "CPU microarchitecture" "${microarchitecture}" \
                "This processor differs from the validated Meteor Lake and AMD Zen 3 profiles; this does not imply different scientific conclusions."
            ;;
    esac
    if diagnostic_haswell_compatible "${architecture}"; then
        diagnostic_add Host ok "OpenBLAS Haswell profile" compatible \
            "Required AVX2 and FMA processor features were detected."
    else
        diagnostic_add Host warning "OpenBLAS Haswell profile" \
            "compatibility not detected" \
            "The Haswell OpenBLAS profile requires amd64 with AVX2 and FMA."
    fi
}

diagnostic_collect_configuration() {
    local configuration="$1"
    local backend="$2"
    local backend_source="$3"
    local logging="$4"
    local logging_source="$5"

    diagnostic_add Configuration ok backend "${backend}" "source: ${backend_source}"
    diagnostic_add Configuration ok logging "${logging}" "source: ${logging_source}"
    if [ -n "${configuration}" ]; then
        diagnostic_add Configuration ok format \
            "$(configuration_format "${configuration}")"
    else
        diagnostic_add Configuration warning format "not selected"
    fi
}

diagnostic_collect_docker() {
    local engine="$1"
    local image="$2"
    local project_path="$3"
    local resources_path="$4"
    local project_selected="$5"
    local client_version
    local image_platform
    local image_digest
    local host_architecture

    if ! command -v "${engine}" >/dev/null 2>&1; then
        diagnostic_add Backend error "Docker CLI" unavailable \
            "Install ${engine} and run diagnostics again."
        return
    fi
    client_version="$("${engine}" version --format '{{.Client.Version}}' 2>/dev/null || true)"
    diagnostic_add Backend ok "Docker CLI" "${client_version:-available}"
    if ! "${engine}" version --format '{{.Server.Version}}' >/dev/null 2>&1; then
        diagnostic_add Backend error "Docker daemon" unreachable \
            "Start Docker and run this command again."
        return
    fi
    diagnostic_add Backend ok "Docker daemon" reachable
    diagnostic_add Runtime ok image "${image}"
    if ! "${engine}" image inspect "${image}" >/dev/null 2>&1; then
        diagnostic_add Runtime error "image availability" missing \
            "Pull ${image} explicitly before running the pipeline."
    else
        image_platform="$("${engine}" image inspect "${image}" \
            --format '{{.Os}}/{{.Architecture}}' 2>/dev/null || true)"
        image_digest="$("${engine}" image inspect "${image}" \
            --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
        diagnostic_add Runtime ok "image platform" "${image_platform:-unknown}"
        diagnostic_add Runtime ok "image digest" "${image_digest:-unavailable}"
        host_architecture="$(uname -m 2>/dev/null || true)"
        if [ -n "${image_platform}" ] \
                && { [[ "${image_platform}" == */amd64 && "${host_architecture}" != x86_64 ]] \
                    || [[ "${image_platform}" == */arm64 && "${host_architecture}" != aarch64 \
                        && "${host_architecture}" != arm64 ]]; }; then
            diagnostic_add Runtime warning "platform execution" emulated \
                "Container execution may require architecture emulation."
        fi
    fi
    if [ -d "${project_path}" ] && [ -r "${project_path}" ] && [ -w "${project_path}" ]; then
        diagnostic_add Runtime ok "project directory mount" available
    elif [ "${project_selected}" != true ]; then
        diagnostic_add Runtime warning "project directory mount" "not checked" \
            "No active project configuration was selected."
    else
        diagnostic_add Runtime error "project directory mount" unavailable \
            "The project directory must be readable and writable."
    fi
    if [ -d "${resources_path}" ] && [ -r "${resources_path}" ] && [ -w "${resources_path}" ]; then
        diagnostic_add Runtime ok "resources directory mount" available
    elif [ "${project_selected}" != true ]; then
        diagnostic_add Runtime warning "resources directory mount" "not checked" \
            "No active project configuration was selected."
    else
        diagnostic_add Runtime error "resources directory mount" unavailable \
            "The resources directory must be readable and writable."
    fi
}

diagnostic_collect_local() {
    local backend="$1"
    local operating_system
    local make_version
    local bash_version
    local manager_version

    operating_system="$(uname -s 2>/dev/null || printf unknown)"
    if [ "${operating_system}" != Linux ]; then
        diagnostic_add Backend error "native execution" unsupported \
            "Use the Docker backend on macOS or Windows."
    else
        diagnostic_add Backend ok "native execution" supported
    fi
    if command -v make >/dev/null 2>&1; then
        make_version="$(diagnostic_version_number make --version)"
        if diagnostic_version_at_least "${make_version}" 4.3; then
            diagnostic_add Runtime ok "GNU Make" "${make_version}"
        else
            diagnostic_add Runtime error "GNU Make" "${make_version:-unknown}" \
                "GNU Make 4.3 or newer is required."
        fi
    else
        diagnostic_add Runtime error "GNU Make" unavailable \
            "Install GNU Make 4.3 or newer."
    fi
    if command -v bash >/dev/null 2>&1; then
        bash_version="$(diagnostic_version_number bash --version)"
        diagnostic_add Runtime ok Bash "${bash_version:-available}"
    else
        diagnostic_add Runtime error Bash unavailable "Install Bash 5 or newer."
    fi
    if command -v "${backend}" >/dev/null 2>&1; then
        manager_version="$(diagnostic_version_number "${backend}" --version)"
        diagnostic_add Backend ok "environment manager" "${backend} ${manager_version}"
        if diagnostic_environment_exists "${backend}" scbolt-system; then
            diagnostic_add Runtime ok "scbolt-system environment" available
        else
            diagnostic_add Runtime error "scbolt-system environment" missing \
                "Reinstall the ${backend} backend."
        fi
    else
        diagnostic_add Backend error "environment manager" "${backend} unavailable" \
            "Install ${backend} or select another backend."
    fi
}

diagnostic_collect_numerical() {
    local seed="$1"
    local core_type="$2"
    local microarchitecture="$3"
    local normalized_core="${core_type^^}"

    diagnostic_add "Numerical reproducibility" ok "BLAS implementation" OpenBLAS
    if [ "${normalized_core}" = HASWELL ]; then
        diagnostic_add "Numerical reproducibility" ok "OpenBLAS core type" Haswell \
            "OPENBLAS_CORETYPE normalises OpenBLAS kernel selection."
    elif [ -z "${core_type}" ]; then
        diagnostic_add "Numerical reproducibility" warning "OpenBLAS core type" unset \
            "The expected value is Haswell; diagnostics do not modify it."
    else
        diagnostic_add "Numerical reproducibility" warning "OpenBLAS core type" "${core_type}" \
            "The expected value is Haswell; diagnostics do not modify it."
    fi
    diagnostic_add "Numerical reproducibility" ok "numerical threads" 1
    diagnostic_add "Numerical reproducibility" ok "random seed" "${seed}"
    diagnostic_add "Numerical reproducibility" ok "UMAP a/b canonicalisation" \
        "8 decimal places"
    case "${microarchitecture}" in
        "Meteor Lake")
            diagnostic_add "Numerical reproducibility" ok "numerical contract" \
                "strict validated (canonical)"
            ;;
        "AMD Zen 3")
            diagnostic_add "Numerical reproducibility" ok "numerical contract" \
                "strict validated"
            ;;
        *)
            diagnostic_add "Numerical reproducibility" warning "numerical contract" portable \
                "Docker fixes the software environment and Haswell normalises OpenBLAS kernels, but different CPU microarchitectures may still introduce small floating-point differences that UMAP and t-SNE can amplify."
            ;;
    esac
}

diagnostic_icon() {
    case "$1" in
        ok) printf '%s✓%s' "${stdout_green}" "${stdout_nc}" ;;
        warning) printf '%s⚠%s' "${stdout_yellow}" "${stdout_nc}" ;;
        error) printf '%s✗%s' "${stderr_red}" "${stderr_nc}" ;;
    esac
}

diagnostic_render() {
    local ordered_sections=(
        scBOLT Host Configuration Backend Runtime
        "Numerical reproducibility"
    )
    local section
    local index
    local printed=false
    local warnings=0
    local errors=0

    for section in "${ordered_sections[@]}"; do
        printed=false
        for index in "${!diagnostic_sections[@]}"; do
            [ "${diagnostic_sections[${index}]}" = "${section}" ] || continue
            if [ "${printed}" = "false" ]; then
                if [ "${index}" -gt 0 ]; then printf '\n'; fi
                printf '%s%s%s\n' "${stdout_bold}" "${section}" "${stdout_nc}"
                printed=true
            fi
            printf '  %s %s: %s\n' \
                "$(diagnostic_icon "${diagnostic_statuses[${index}]}")" \
                "${diagnostic_names[${index}]}" \
                "${diagnostic_values[${index}]}"
            if [ -n "${diagnostic_details[${index}]}" ]; then
                printf '    %s\n' "${diagnostic_details[${index}]}"
            fi
            case "${diagnostic_statuses[${index}]}" in
                warning) warnings=$((warnings + 1)) ;;
                error) errors=$((errors + 1)) ;;
            esac
        done
    done
    printf '\n%sStatus%s\n' "${stdout_bold}" "${stdout_nc}"
    if [ "${errors}" -gt 0 ]; then
        printf '  Not operational: %d blocking error%s' \
            "${errors}" "$([ "${errors}" -eq 1 ] || printf s)"
        if [ "${warnings}" -gt 0 ]; then
            printf ' and %d warning%s' "${warnings}" \
                "$([ "${warnings}" -eq 1 ] || printf s)"
        fi
        printf '.\n'
        return 1
    fi
    if [ "${warnings}" -gt 0 ]; then
        printf '  Operational with %d warning%s.\n' \
            "${warnings}" "$([ "${warnings}" -eq 1 ] || printf s)"
    else
        printf '  Operational.\n'
    fi
}

run_diagnostics() {
    local configuration=""
    local configuration_path=""
    local configuration_base="${PWD}"
    local backend_override=""
    local backend
    local backend_source
    local logging
    local logging_source
    local project_dir
    local resources_dir
    local project_path
    local resources_path
    local image
    local engine
    local seed
    local core_type
    local processor
    local microarchitecture
    local configuration_issue=""
    local argument

    while [ "$#" -gt 0 ]; do
        argument="$1"
        shift
        case "${argument}" in
            -h|--help|help)
                diagnostics_help
                return 0
                ;;
            --config=*|--params=*) configuration="${argument#*=}" ;;
            --config|--params)
                if [ "$#" -eq 0 ]; then
                    print_error "Missing value for ${argument}"
                    return 2
                fi
                configuration="$1"
                shift
                ;;
            --backend=*) backend_override="${argument#*=}" ;;
            --backend)
                if [ "$#" -eq 0 ]; then
                    print_error "Missing value for --backend"
                    return 2
                fi
                backend_override="$1"
                shift
                ;;
            *)
                print_error "Usage: scbolt diagnostics"
                return 2
                ;;
        esac
    done
    if [ -z "${configuration}" ]; then
        configuration="$(resolve_project_params 2>/dev/null || true)"
    fi
    if [ -n "${configuration}" ]; then
        configuration_path="$(diagnostic_resolve_path "${configuration}")"
        configuration_base="$(dirname "${configuration_path}")"
        if [ ! -f "${configuration_path}" ]; then
            configuration_issue="Select an existing configuration file."
            configuration=""
        elif [ "$(configuration_format "${configuration_path}" 2>/dev/null || true)" = yaml ]; then
            if ! run_project_config_helper export "${configuration_path}" \
                    >/dev/null 2>&1; then
                configuration_issue="Fix the invalid YAML configuration and run diagnostics again."
                configuration=""
            fi
        fi
    fi

    backend="${backend_override:-$(diagnostic_project_value "${configuration_path}" BACKEND "${SCBOLT_DEFAULT_BACKEND:-conda}")}"
    backend_source="$(diagnostic_project_source "${configuration_path}" BACKEND)"
    [ -z "${backend_override}" ] || backend_source=CLI
    logging="$(diagnostic_project_value "${configuration_path}" LOGGING true)"
    logging_source="$(diagnostic_project_source "${configuration_path}" LOGGING)"
    project_dir="$(diagnostic_project_value "${configuration_path}" PROJECT_DIR project)"
    resources_dir="$(diagnostic_project_value "${configuration_path}" RESOURCES_DIR resources)"
    project_path="$(diagnostic_resolve_path "${project_dir}" "${configuration_base}")"
    resources_path="$(diagnostic_resolve_path "${resources_dir}" "${configuration_base}")"

    diagnostic_collect_scbolt "${configuration}" "${configuration_path}" \
        "${configuration_base}" "${project_dir}" "${resources_dir}" \
        "${configuration_issue}"
    diagnostic_collect_host
    diagnostic_collect_configuration "${configuration}" "${backend}" \
        "${backend_source}" "${logging}" "${logging_source}"
    if [ "${backend}" = docker ]; then
        image="$(diagnostic_project_value "${configuration_path}" SCBOLT_IMAGE \
            ghcr.io/bnediction/scbolt:latest)"
        engine="$(diagnostic_project_value "${configuration_path}" \
            SCBOLT_CONTAINER_ENGINE docker)"
        diagnostic_collect_docker "${engine}" "${image}" "${project_path}" \
            "${resources_path}" "$([ -n "${configuration}" ] && printf true || printf false)"
    elif [[ " ${backend} " == *" conda "* || " ${backend} " == *" mamba "* \
            || " ${backend} " == *" micromamba "* ]]; then
        diagnostic_collect_local "${backend}"
    else
        diagnostic_add Backend error backend "${backend}" \
            "Supported values are conda, mamba, micromamba, and docker."
    fi
    seed="$(diagnostic_project_value "${configuration_path}" SEED 0)"
    core_type="${OPENBLAS_CORETYPE:-$(diagnostic_project_value \
        "${configuration_path}" OPENBLAS_CORETYPE "")}"
    if [ -z "${core_type}" ] \
            && diagnostic_haswell_compatible "$(uname -m 2>/dev/null || true)"; then
        core_type=Haswell
    fi
    processor="$(diagnostic_cpu_model)"
    microarchitecture="$(diagnostic_microarchitecture "${processor}")"
    diagnostic_collect_numerical "${seed}" "${core_type}" "${microarchitecture}"
    diagnostic_render
}
