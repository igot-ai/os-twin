#!/bin/bash
export PYTHONPATH=$PYTHONPATH:.
uvicorn api:app --port 9001 > server.log 2>&1 &
SERVER_PID=$!
sleep 5
python3 test_endpoints.py
kill $SERVER_PID
cat server.log
