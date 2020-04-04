#!/bin/bash
	

## example 1: checking if "python3" is running
while :
do
OUTPUT=$(ps -aux | grep -cE "python3")

if (( OUTPUT > 1 )); then
    echo "python3 is running"
	sleep 30s
else
    echo "python3 is not running"
	
    sudo nohup python3 /deribitBitmexMarketMaker_ByFunding_private/real_poc_from_env_master.py &
fi


done