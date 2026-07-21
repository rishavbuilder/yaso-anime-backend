#!/bin/bash
cd "$(dirname "$0")"
kill $(pgrep -f uvicorn) 2>/dev/null
sleep 1
nohup python3 -m uvicorn anime_scraper:app --host 0.0.0.0 --port 8000 >> /tmp/yaso.log 2>&1 &
echo "Server started on http://localhost:8000 (PID: $!)"
