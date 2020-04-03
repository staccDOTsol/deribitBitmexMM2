#!/bin/bash
while :
do
sudo killall python3
sudo nohup python3 "real_poc_from_env_master.py" &
sleep 60m
done