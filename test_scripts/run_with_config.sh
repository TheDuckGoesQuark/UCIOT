#!/usr/bin/env bash

DEFAULT_CONFIG_FILE_PATH="./test_configs/config.ini"
config_file_path="$1"

if [[ -z "${config_file_path}" ]]; then
    echo "WARN - No config file provided. Will use defaults at "
    config_file_path="${DEFAULT_CONFIG_FILE_PATH}"
fi

python3 -u ../__main__.py "${config_file_path}"
