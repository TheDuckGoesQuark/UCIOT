#!/usr/bin/env bash

nMachines=40
machine_list_file="up_machines.txt"

# Read contents of file into array
mapfile -t machines < ${machine_list_file}

nMachines=${#machines[@]}

for i in "${!machines[@]}"; do
    ssh -o ConnectTimeout=3 jm354@${machines[i]} "export UCIOT_CONT=0;" &
    if [[ ${i} -eq ${nMachines} ]]; then
        break;
    fi
done

echo "Waiting..."
wait


