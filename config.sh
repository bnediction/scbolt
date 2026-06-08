#!/usr/bin/bash

scbolt_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
env_dir="${scbolt_root}/envs"
lib_dir="${scbolt_root}/lib"
scbolt_command="${scbolt_root}/bin/scbolt"
scbolt_completion="${scbolt_root}/bin/completion.bash"
local_bin="${HOME}/.local/bin"
local_completion_dir="${HOME}/.local/share/bash-completion/completions"

bonesis_hash="${BONESIS_HASH:-d70736703af2fa8a88306ac66626b4876d5c5839}"
scvelo_hash="${SCVELO_HASH:-b2f31b345641efdccd39fbcb8c0beaa0014b4b88}"

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

install_env() {
    if conda env list | grep -q "^$1 ";
    then
        echo "Conda environment '$1' already exists"
        read -r -p $"Do you want to reinstall conda environment '${1}'? ([y]/n): " choice
        if [[ $choice == "y" || -z $choice ]];
        then
            conda remove --name "$1" --all --yes
            conda env create -f "$2" --yes
            if [ "$1" != "scbolt-fastq" ] && [ "$1" != "scbolt-velocyto" ];
            then
                conda develop --name "$1" "${lib_dir}";
            fi
            if [ "$1" == "scbolt-bonesis" ];
            then
                install_bonesis_git "$1"
            fi

        else
            echo -e "Conda environment '$1' not reinstalled.\n"
        fi
    else
        echo "Installing conda environment '$1'"
        conda env create -f "$2"
        conda develop --name "$1" "${lib_dir}";
        if [ "$1" == "scbolt-bonesis" ];
        then
            install_bonesis_git "$1"
        fi
    fi
}

install_scbolt_command() {
    local choice

    if [ ! -x "${scbolt_command}" ];
    then
        echo "scBOLT command not found: ${scbolt_command}"
        return
    fi

    read -r -p $"Install the scbolt command in ~/.local/bin? ([y]/n): " choice
    if [[ $choice != "y" && $choice != "Y" && $choice != "yes" && -n $choice ]];
    then
        echo "scBOLT command not installed."
        return
    fi

    mkdir -p "${local_bin}"
    ln -sfn "${scbolt_command}" "${local_bin}/scbolt"

    echo "Installed:"
    echo "  ${local_bin}/scbolt -> ${scbolt_command}"

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

install_scbolt_command
install_scbolt_completion
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
