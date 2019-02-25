#!/usr/bin/env bash

nMachines=40
machine_list_file="up_machines.txt"

# Read contents of file into array
mapfile -t machines < ${machine_list_file}

nMachines=${#machines[@]}

mkdir ~/killswitch


