#!/bin/bash
set -e

echo '============================================'
echo '  TradeMatrix Deploy Script'
echo '============================================'

APP_DIR=/home/ikkishprep/app

echo '[1/4] Pulling latest code from GitHub...'
cd $APP_DIR
git fetch origin main
git reset --hard origin/main
echo 'Code updated!'

echo '[2/4] Checking disk space...'
df -h / | awk 'NR==2 {print "Disk Usage: " $5 " used, " $4 " free"}'

echo '[3/4] Rebuilding Docker containers...'
sudo docker-compose up -d --build

echo '[4/4] Checking container health...'
sleep 5
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo '============================================'
echo '  Deploy complete!'
echo '============================================'
