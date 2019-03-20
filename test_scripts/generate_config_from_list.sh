#!/usr/bin/env bash

if [[ "$1" -eq "-h" ]]; then
    me=`basename $0`
    echo "Usage: ./${me} list_file_path sink_loc sink_id"
    exit 1
fi


list_file=$1
if [[ -z "${list_file}" ]] || [[ ! -f "${list_file}" ]]; then
    echo "List file missing or doesn't exist: ${list_file}"
    exit 1
fi

sink_locator=$2
if [[ -z "${sink_locator}" ]]; then
    echo "No sink locator supplied as second argument"
    exit 1
fi

sink_id=$3
if [[ -z "${sink_id}" ]]; then
    echo "No sink Id supplied as third argument"
    exit 1
fi


target_file=${list_file/_list.txt/.ini}

if [[ -e ${target_file} ]]; then
    > "${target_file}"
fi

read -r -d '' TEMPLATE << EOM
[NAME]
group_ids = LOCS
my_id = ID
sink_loc = SINK_LOC
sink_id = SINK_ID
router_refresh_delay_secs = 3
unique_identifier=
port = 8080
hop_limit = 8
packet_buffer_size_bytes = 4096
loopback = no
max_sends = 1000000
save_file_loc = test.csv
send_delay_secs = 1
number_of_paths = 2
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
    CONFIG=${CONFIG/SINK_ID/$sink_id}
    CONFIG=${CONFIG/SINK_LOC/$sink_locator}
    CONFIG=${CONFIG/ID/$id}
    CONFIG=${CONFIG/NAME/$config_name}
    echo "$CONFIG" >> ${target_file}
    echo -e "\n" >> ${target_file}
done

echo "Configuration file created in ${target_file}"
