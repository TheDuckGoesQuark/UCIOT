#!/usr/bin/env bash

# Remove killswitch
rmdir ~/killswitch

projectDir="/cs/home/jm354/Documents/Uni/Y4/SH/UCIOT"

# Remove results files
rm "${projectDir}"/test.csv
rm "${projectDir}"/sink_log.csv

# Clear log files
for file in ${projectDir}/logs/*; do
    > "${file}"
done
