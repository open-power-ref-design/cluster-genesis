#!/bin/bash

http_server=$1

pxe_ip=$(ip route get $http_server | head -n 1 | sed 's/.*src //' | \
    sed 's/[[:space:]]*$//')
pxe_dev=$(ip route get $http_server | head -n 1 | sed 's/.*dev //' | \
    sed 's/[[:space:]]*src.*$//')

printf "{\n" > /tmp/pup_report.txt

printf "  \"pup_pxe_ipaddr\" : \"${pxe_ip}\",\n" >> /tmp/pup_report.txt
printf "  \"pup_pxe_dev\" : \"${pxe_dev}\",\n" >> /tmp/pup_report.txt
printf "  \"pup_pxe_mac\" : \"$(cat /sys/class/net/$pxe_dev/address)\"," >> \
    /tmp/pup_report.txt

comma=false
for file in 'os-release'; do
    while read line; do
        if [ "$line" != "" ]; then
            json_line=$(echo $line | sed 's/"//g' | sed 's/=/\": \"/')
            if $comma; then
                printf ",\n  \"${json_line}\"" >> /tmp/pup_report.txt
            else
                printf "\n  \"${json_line}\"" >> /tmp/pup_report.txt
            fi
        fi
        comma=true
    done < /etc/$file
done

for channel in 1 8; do
    ipmitool lan print > /tmp/pup_ipmitool_lan_print${channel}.txt
    printf ",\n  \"ipmitool_lan_print_$channel\": {" >> /tmp/pup_report.txt
    comma=false
    while read line; do
        if [ "$line" != "" ]; then
            json_line=$(echo $line | sed 's/\s*:\s*/\": \"/')
            if [[ $json_line == '": "'* ]]; then
                printf "; ${json_line#*\ \"}" >> /tmp/pup_report.txt
            elif $comma; then
                printf "\",\n    \"${json_line}" >> /tmp/pup_report.txt
            else
                printf "\n    \"${json_line}" >> /tmp/pup_report.txt
            fi
        fi
        comma=true
    done < /tmp/pup_ipmitool_lan_print${channel}.txt
    printf "\"\n  }" >> /tmp/pup_report.txt
done

ipmitool fru print > /tmp/pup_ipmitool_fru_print.txt
sed -i '$ {/^$/d;}' /tmp/pup_ipmitool_fru_print.txt
printf ",\n  \"ipmitool_fru_print\": [\n    {" >> /tmp/pup_report.txt
comma=false
while read line; do
    if [ "$line" != "" ]; then
        json_line=$(echo $line | sed 's/\s*:\s*/\": \"/')
        if [[ $json_line != *':'* ]]; then
            printf "\",\n      \"msg\": \"${json_line}" >> /tmp/pup_report.txt
        elif $comma; then
            printf "\",\n      \"${json_line}" >> /tmp/pup_report.txt
        else
            printf "\n      \"${json_line}" >> /tmp/pup_report.txt
        fi
        comma=true
    else
        printf "\"\n    },\n" >> /tmp/pup_report.txt
        printf "    {" >> /tmp/pup_report.txt
        comma=false
    fi
done < /tmp/pup_ipmitool_fru_print.txt
printf "\"\n    }" >> /tmp/pup_report.txt
printf "\n  ]" >> /tmp/pup_report.txt

printf "\n}\n" >> /tmp/pup_report.txt
