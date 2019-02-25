#!/usr/bin/env bash

list_file=$1
target_file=$2

read -r -d '' TEMPLATE << EOM
[NAME]
group_ids = LOCS
my_id = ID
is_sink = true
sink_loc = 0
sink_id = 1
router_refresh_delay_secs = 120
unique_identifier=
port = 8080
hop_limit = 32
sleep = 3
packet_buffer_size_bytes = 4096
loopback = no
max_sends = 1000
save_file_loc = "test.csv"
send_delay_secs = 10

EOM

mapfile -t config_names < ${list_file}

for config_name in ${config_names[@]}; do
    CONFIG="${TEMPLATE}"
    # Isolate variables
    locators=${config_name#LOC_}
    locators=${locators%_ID*}
    locators=${locators//_/,}
    id=${config_name#*_ID_}

    echo "creating config for $locators and $id"
    CONFIG=${CONFIG/LOCS/$locators}
    CONFIG=${CONFIG/ID/$id}
    CONFIG=${CONFIG/NAME/$config_name}
    echo "$CONFIG" >> ${target_file}
    echo -e "\n" >> ${target_file}
done
