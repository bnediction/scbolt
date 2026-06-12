#!/usr/bin/bash

set -e

scbolt_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
env_dir="${scbolt_root}/envs"
lib_dir="${scbolt_root}/lib"
scbolt_command="${scbolt_root}/bin/scbolt"
scbolt_completion="${scbolt_root}/bin/completion.bash"
local_bin="${HOME}/.local/bin"
local_completion_dir="${HOME}/.local/share/bash-completion/completions"

bonesis_hash="${BONESIS_HASH:-d70736781f88faee334ef79622e144216837f4c5}"
scvelo_hash="${SCVELO_HASH:-b2f31b345641efdccd39fbcb8c0beaa0014b4b88}"

if [ -t 1 ];
then
    stdout_green=$'\033[0;32m'
    stdout_yellow=$'\033[0;33m'
    stdout_nc=$'\033[0m'
else
    stdout_green=""
    stdout_yellow=""
    stdout_nc=""
fi

if [ -t 2 ];
then
    stderr_red=$'\033[0;31m'
    stderr_nc=$'\033[0m'
else
    stderr_red=""
    stderr_nc=""
fi

print_install_success() {
    printf '%s✓%s %s successfully installed.\n' "${stdout_green}" "${stdout_nc}" "$1"
}

print_install_warning() {
    printf '%s⚠%s %s not reinstalled.\n' "${stdout_yellow}" "${stdout_nc}" "$1"
}

print_install_failure() {
    printf '%s✗%s %s failed to install.\n' "${stderr_red}" "${stderr_nc}" "$1" >&2
}

handle_interrupt() {
    trap - INT TERM
    echo >&2
    printf '%s✗%s installation cancelled by user.\n' "${stderr_red}" "${stderr_nc}" >&2
    exit 130
}

trap handle_interrupt INT TERM

return_or_interrupt() {
    local status="$1"

    if [ "${status}" -ge 128 ];
    then
        handle_interrupt
    fi

    return "${status}"
}

run_quiet() {
    local logfile
    local status

    logfile=$(mktemp)
    if "$@" >"${logfile}" 2>&1;
    then
        rm -f "${logfile}"
        return 0
    fi

    status=$?
    if [ "${status}" -ge 128 ];
    then
        rm -f "${logfile}"
        handle_interrupt
    fi

    cat "${logfile}" >&2
    rm -f "${logfile}"
    return_or_interrupt "${status}"
}

install_bonesis_git() {
    conda run --no-capture-output -n "$1" python -m pip install \
        --force-reinstall \
        --no-deps \
        "git+https://github.com/bnediction/bonesis.git@${bonesis_hash}"
}

install_scvelo_git() {
    conda run --no-capture-output -n "$1" python -m pip install \
        "git+https://github.com/theislab/scvelo.git@${scvelo_hash}"
}

develop_scbolt_lib() {
    if [ "$1" == "scbolt-align" ];
    then
        return 0
    fi

    run_quiet conda develop --name "$1" "${lib_dir}"
}

configure_env() {
    develop_scbolt_lib "$1" || return_or_interrupt "$?"

    if [ "$1" == "scbolt-bonesis" ];
    then
        install_bonesis_git "$1" || return_or_interrupt "$?"
    fi
}

install_env_steps() {
    local env="$1"
    local env_file="$2"

    echo "creating conda environment '${env}'."
    echo "resolving conda environment '${env}'."
    run_quiet conda env create -f "${env_file}" --yes || return_or_interrupt "$?"
    configure_env "${env}" || return_or_interrupt "$?"
}

install_env() {
    local status

    if conda env list | grep -q "^$1 ";
    then
        echo "conda environment '$1' already exists."
        read -r -p $"Do you want to reinstall conda environment '${1}'? ([y]/n): " choice
        if [[ $choice == "y" || -z $choice ]];
        then
            echo "removing conda environment '$1'."
            if run_quiet conda remove --name "$1" --all --yes && install_env_steps "$1" "$2";
            then
                print_install_success "$1"
                echo
            else
                status=$?
                return_or_interrupt "${status}"
                print_install_failure "$1"
                return 1
            fi

        else
            print_install_warning "$1"
            echo
        fi
    else
        if install_env_steps "$1" "$2";
        then
            print_install_success "$1"
            echo
        else
            status=$?
            return_or_interrupt "${status}"
            print_install_failure "$1"
            return 1
        fi
    fi
}

install_scbolt_command() {
    local choice
    local installed_command="${local_bin}/scbolt"

    if [ ! -x "${scbolt_command}" ];
    then
        echo "scBOLT command not found: ${scbolt_command}"
        return 1
    fi

    read -r -p $"Install the scbolt command in ~/.local/bin? ([y]/n): " choice
    if [[ $choice != "y" && $choice != "Y" && $choice != "yes" && -n $choice ]];
    then
        if [ -e "${installed_command}" ];
        then
            echo "scBOLT command unchanged:"
            echo "  ${installed_command}"
        else
            echo "scBOLT command not installed."
        fi
        return 1
    fi

    mkdir -p "${local_bin}"
    ln -sfn "${scbolt_command}" "${installed_command}"

    echo "Installed:"
    echo "  ${installed_command} -> ${scbolt_command}"

    case ":${PATH}:" in
        *":${local_bin}:"*) ;;
        *)
            echo
            echo "Add this line to your shell configuration:"
            echo
            # shellcheck disable=SC2016
            echo 'export PATH="$HOME/.local/bin:$PATH"'
            ;;
    esac

    return 0
}

install_scbolt_completion() {
    if [ ! -f "${scbolt_completion}" ];
    then
        echo "scBOLT Bash completion not found: ${scbolt_completion}"
        return
    fi

    mkdir -p "${local_completion_dir}"
    ln -sfn "${scbolt_completion}" "${local_completion_dir}/scbolt"

    echo "Installed Bash completion:"
    echo "  ${local_completion_dir}/scbolt -> ${scbolt_completion}"
    echo
    echo "Restart your shell, or run:"
    echo
    echo "  source ${local_completion_dir}/scbolt"
}

if install_scbolt_command;
then
    install_scbolt_completion
fi
echo

# shellcheck source=/dev/null
source "$(conda info --base)/etc/profile.d/conda.sh"

if conda env list | grep -q "^base";
then
    conda activate base
fi

for file in "${env_dir}"/*.yml
do
    env=scbolt-$(basename "${file%.yml}")
    install_env "$env" "$file"
done
