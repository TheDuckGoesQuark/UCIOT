#!/usr/bin/env bash

DEFAULT_CONFIG_FILE_PATH="./configs/config.ini"
DEFAULT_CONFIG_FILE_SECTION="DEFAULT"
config_file_path="$1"
config_file_section="$2"

if [[ -z "${config_file_path}" ]]; then
    echo "WARN - No config file provided. Will use defaults at ${DEFAULT_CONFIG_FILE_PATH}"
    config_file_path="${DEFAULT_CONFIG_FILE_PATH}"
fi

if [[ -z "${config_file_section}" ]]; then
    echo "WARN - No config file section provided. Will use defaults ${DEFAULT_CONFIG_FILE_SECTION}"
    config_file_section="${DEFAULT_CONFIG_FILE_SECTION}"
fi

python3 -u ../__main__.py "${config_file_path}" "${config_file_section}"

