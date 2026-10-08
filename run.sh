#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 job_hunter.py >> logs/scheduler.log 2>&1
