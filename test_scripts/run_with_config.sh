#!/usr/bin/env bash

config_file_path="$1"
config_file_section="$2"

if [[ -z "${config_file_path}" ]]; then
    echo "No config file provided. "
    exit 1
fi

if [[ -z "${config_file_section}" ]]; then
    echo "No config file section provided. "
    exit 1
fi

python3 -u /home/jordan/Documents/Uni/sh/UCIOT/__main__.py "${config_file_path}" "${config_file_section}"

