#!/usr/bin/env bash

if [[ "$1" == "-h" ]]; then
    me=`basename $0`
    echo "Usage: ./${me} list_file_path sink_id"
    exit 1
fi


list_file=$1
if [[ -z "${list_file}" ]] || [[ ! -f "${list_file}" ]]; then
    echo "List file missing or doesn't exist: ${list_file}"
    exit 1
fi

sink_id=$2
if [[ -z "${sink_id}" ]]; then
    echo "No sink Id supplied as second argument"
    exit 1
fi

target_file=${list_file/_list.txt/.ini}

if [[ -e ${target_file} ]]; then
    > "${target_file}"
fi

read -r -d '' TEMPLATE << EOM
[NAME]
port=8080
packet_buffer_size=512
loopback=False
mcast_groups=MCAST
my_id=ID
my_locator=LOC
max_packet_sends=300
sink_id=SINK_ID
interval=5
sink_log=sink.csv
results_file=results.csv
EOM

mapfile -t config_names < ${list_file}

echo "Using $list_file as source"
for config_name in ${config_names[@]}; do
    # Isolate variables
    locator=${config_name%_ID*}
    locator=${locator#LOC_}
    id=${config_name%%_MCAST*}
    id=${id##*_ID_}
    mcast=${config_name##*MCAST_}
    mcast=${mcast//_/,}

    echo "creating config for $locator:$id, groups:$mcast"
    CONFIG="${TEMPLATE}"
    CONFIG=${CONFIG/LOC/$locator}
    CONFIG=${CONFIG/SINK_ID/$sink_id}
    CONFIG=${CONFIG/ID/$id}
    CONFIG=${CONFIG/MCAST/$mcast}
    CONFIG=${CONFIG/NAME/$config_name}
    echo "$CONFIG" >> ${target_file}
    echo -e "\n" >> ${target_file}
done

echo "Configuration file created in ${target_file}"
