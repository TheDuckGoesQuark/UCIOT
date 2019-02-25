#!/usr/bin/env bash

working_list_file="up_machines.txt"
# Clear file if exists from previous experiment
if [[ -e ${working_list_file} ]]; then
    > ${working_list_file}
fi

machines=(
    138.251.29.10
    138.251.29.11
    138.251.29.12
    138.251.29.13
    138.251.29.14
    138.251.29.15
    138.251.29.16
    138.251.29.17
    138.251.29.18
    138.251.29.19
    138.251.29.20
    138.251.29.21
    138.251.29.22
    138.251.29.23
    138.251.29.24
    138.251.29.25
    138.251.29.26
    138.251.29.27
    138.251.29.28
    138.251.29.29
    138.251.29.30
    138.251.29.31
    138.251.29.32
    138.251.29.33
)
#    138.251.29.34
#    138.251.29.35
#    138.251.29.36
#    138.251.29.37
#    138.251.29.38
#    138.251.29.39
#    138.251.29.40
#    138.251.29.41
#    138.251.29.42
#    138.251.29.43
#    138.251.29.44
#    138.251.29.45
#    138.251.29.46
#    138.251.29.47
#    138.251.29.48
#    138.251.29.49
#    138.251.29.50
#    138.251.29.51
#    138.251.29.52
#    138.251.29.53
#    138.251.29.54
#    138.251.29.55
#    138.251.29.56
#    138.251.29.57
#    138.251.29.58
#    138.251.29.59
#    138.251.29.60
#    138.251.29.61
#    138.251.29.62
#    138.251.29.63
#    138.251.29.64
#    138.251.29.65
#    138.251.29.66
#    138.251.29.67
#    138.251.29.68
#    138.251.29.69
#    138.251.29.70
#    138.251.29.71
#    138.251.29.72
#    138.251.29.73
#    138.251.29.74
#    138.251.29.75
#    138.251.29.76
#    138.251.29.77
#    138.251.29.78
#    138.251.29.79
#    138.251.29.80
#    138.251.29.81
#    138.251.29.82
#    138.251.29.83
#    138.251.29.84
#    138.251.29.85
#    138.251.29.86
#    138.251.29.87
#    138.251.29.88
#    138.251.29.89
#    138.251.29.90
#    138.251.29.91
#    138.251.29.92
#    138.251.29.93
#    138.251.29.94
#    138.251.29.95
#    138.251.29.96
#    138.251.29.97
#    138.251.29.98
#    138.251.29.99
#    138.251.29.100
#    138.251.29.101
#    138.251.29.102
#    138.251.29.103
#    138.251.29.104
#    138.251.29.105
#    138.251.29.106
#    138.251.29.107
#    138.251.29.108
#    138.251.29.109
#    138.251.29.110
#    138.251.29.111
#    138.251.29.112
#    138.251.29.113
#    138.251.29.114
#    138.251.29.115
#    138.251.29.116
#    138.251.29.117
#    138.251.29.118
#    138.251.29.119
#    138.251.29.120
#    138.251.29.121
#    138.251.29.122
#    138.251.29.123
#    138.251.29.124
#    138.251.29.125
#    138.251.29.126
#    138.251.29.127
#    138.251.29.128
#    138.251.29.129
#    138.251.29.130
#    138.251.29.131
#    138.251.29.132
#    138.251.29.133
#    138.251.29.134
#    138.251.29.135
#    138.251.29.136
#    138.251.29.137
#    138.251.29.138
#    138.251.29.139
#    138.251.29.140
#    138.251.29.141
#    138.251.29.142
#    138.251.29.143
#    138.251.29.144
#    138.251.29.145
#    138.251.29.146
#    138.251.29.147
#    138.251.29.148
#    138.251.29.149
#    138.251.29.150
#    138.251.29.151
#    138.251.29.152
#    138.251.29.153
#    138.251.29.154
#    138.251.29.155
#    138.251.29.156
#    138.251.29.157
#    138.251.29.158
#    138.251.29.159
#    138.251.29.162
#    138.251.29.163
#    138.251.29.164
#    138.251.29.165
#    138.251.29.166
#    138.251.29.167
#    138.251.29.168
#    138.251.29.169
#    138.251.29.170
#    138.251.29.171
#    138.251.29.172
#    138.251.29.173
#    138.251.29.174
#    138.251.29.175
#    138.251.29.176
#    138.251.29.177
#    138.251.29.178
#    138.251.29.179
#    138.251.29.180
#    138.251.29.181
#    138.251.29.182
#    138.251.29.183
#    138.251.29.184
#    138.251.29.185
#    138.251.29.186
#    138.251.29.187
#    138.251.29.188
#    138.251.29.189
#    138.251.29.190
#    138.251.29.191
#    138.251.29.192
#    138.251.29.193
#    138.251.29.194
#    138.251.29.195
#    138.251.29.196
#    138.251.29.197
#    138.251.29.198
#    138.251.29.199
#    138.251.29.200
#    138.251.29.201
#    138.251.29.202
#    138.251.29.203
#    138.251.29.204
#    138.251.29.205
#    138.251.29.206
#    138.251.29.207
#    138.251.29.208
#    138.251.29.209
#    138.251.29.210
#    138.251.29.211
#    138.251.29.212
#    138.251.29.213
#    138.251.29.214
#    138.251.29.215
#    138.251.29.216
#    138.251.29.217
#    138.251.29.218
#    138.251.29.219
#    138.251.29.220
#    138.251.29.221
#    138.251.29.222
#    138.251.29.223
#    138.251.29.224
#    138.251.29.225
#    138.251.29.226
#    138.251.29.227
#    138.251.29.228
#    138.251.29.229
#    138.251.29.230
#    138.251.29.231
#    138.251.29.232
#    138.251.29.233
#    138.251.29.234
#    138.251.29.239
#    138.251.29.240
#    138.251.29.241
#    138.251.29.242
#    138.251.29.243
#    138.251.29.244
#    138.251.29.245
#    138.251.29.246
#    138.251.29.247
#    138.251.29.248
#    138.251.29.249
#    138.251.29.250
#    138.251.29.251
#    138.251.28.2
#    138.251.28.4
#    138.251.28.6
#    138.251.28.8
#    138.251.29.1
#    138.251.29.3
#    138.251.29.5
#    138.251.29.9
#    138.251.30.66
#    138.251.30.68
#    138.251.30.70
#    138.251.30.72
#    138.251.30.74
#    138.251.30.76
#    138.251.30.78
#    138.251.30.80
#    138.251.30.82
#    138.251.30.84
#    138.251.30.86
#    138.251.30.88
#    138.251.30.90
#    138.251.30.92
#    138.251.30.94
#    138.251.30.96
#    138.251.30.98
#    138.251.30.100
#    138.251.30.102
#)

echo "Testing ${#machines[@]} machines using ping"

# Test for active machines
to_remove=()
n=0
for m in ${machines[@]}; do
    echo "Pinging machine $n"
    ping -c 1 $m;

    if [[ $? -ne 0 ]]; then
        echo "Unable to connect to $m"
        to_remove+=("$m")
    fi
    let n++
done

# Remove unreachable machines
for del in ${to_remove[@]}; do
    echo "Removing $del"
    machines=("${machines[@]/$del}")
done

# write reachable machines to file
n=0
for m in ${machines[@]}; do
    echo "Add $m to file"
    printf "%s\n" "$m" >> "${working_list_file}"
    let n++
done

echo "$n working machines listed in ${working_list_file}"
