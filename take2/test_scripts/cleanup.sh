#!/usr/bin/env bash

# Remove killswitch
rmdir ~/killswitch

projectDir="/cs/home/jm354/Documents/Uni/Y4/SH/UCIOT/take2"

# Remove results files
rm "${projectDir}"/results.csv
rm "${projectDir}"/sink.csv

# Clear log files
for file in ${projectDir}/logs/*; do
    > "${file}"
done
