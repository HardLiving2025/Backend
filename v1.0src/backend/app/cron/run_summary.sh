#!/bin/bash

# v0.6src/backend 폴더 기준으로 실행
cd /home/t25335/v0.6src/backend

# Python 실행 (backend/app/cron/generate_daily_summary.py)
# 로그는 daily_summary.log로 저장
/usr/bin/python3 app/cron/generate_daily_summary.py >> app/cron/daily_summary.log 2>&1
