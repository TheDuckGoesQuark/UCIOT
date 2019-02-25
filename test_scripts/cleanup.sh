#!/usr/bin/env bash

machine_list_file="up_machines.txt"

# Read contents of file into array
mapfile -t machines < ${machine_list_file}

nMachines=${#machines[@]}

for machine in "${machines[@]}"; do
    ssh ${machine} "export UCIOT_CONT=0;" &
    echo "Status code: $?"
done

wait


