#!/usr/bin/env bash

config_list_file=$1
config_file=${config_list_file/_list.txt/.ini}
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

echo "Detected $nMachines machines and $nConfigs configurations"
# Check enough resources to run experiment
if [[ ${nMachines} -lt ${nConfigs} ]]; then
    echo "Not enough machines to run experiment";
    missing=$(( $nConfigs - $nMachines ))
    echo "Need $missing more machines"
    exit 1
fi

for i in "${!configs[@]}"; do
    config="${configs[$i]}"
    machine="${machines[$i]}"

    project_path="/cs/home/jm354/Documents/FourthYear/SH/UCIOT"
    run_script="${project_path}/test_scripts/run_with_config.sh"
    config_path="${project_path}/test_scripts/configs/${config_file}"

    number=$((i + 1))
    echo "$number/$nConfigs: Running config ${config} on machine ${machine}"
    echo ${run_script}
    echo ${config_path}
    echo ${config}
    #ssh ${machine} "${run_script} ${config_path} ${config}"

done
