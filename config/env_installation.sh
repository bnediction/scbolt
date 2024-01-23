[ -d "config" ] && config_dir="config" || config_dir=""

install_env() {
    if conda env list | grep -q "^$1 ";
    then
        read -p "$1 conda env already exists. do you want to reinstall $1 env? ([y]/n): " choice
        if [[ "$choice" == "y" || -z "$choice" ]];
        then
            conda env create -f ${config_dir}/$1.yml
        else
            echo "$1 env not reinstalled."
        fi
    else
        conda env create -f ${config_dir}/$1.yml
    fi
}

install_env preprocess
install_env stream
