#!/usr/bin/env bash

config_list_file=$1
machine_list_file="up_machines.txt"

if [[ -z ${config_list_file} ]]; then
    echo "File containing list of configurations to use missing."
    exit 1
fi

# Read contents of both files into arrays
mapfile -t configs < ${config_list_file}
mapfile -t machines < ${machine_list_file}

nMachines=${#machines[@]}
nConfigs=${#configs[@]}

# Check enough resources to run experiment
if [[ ${nMachines} -lt ${nConfigs} ]]; then
    echo "Not enough machines to run experiment";
    missing=$(( $nConfigs - $nMachines ))
    echo "Need $missing more machines"
fi

for i in {0..${#configs[@]}}; do
    echo "Running config ${configs[$i]} on machine ${machines[$i]}"
done
