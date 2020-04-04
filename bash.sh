#!/bin/bash
while :
do
sudo killall python3
nohup python3 /deribitBitmexMarketMaker_ByFunding_private/real_poc_from_env_master.py &
sleep 60m
done