#!/bin/bash
export PYTHONPATH=$PYTHONPATH:.
uvicorn api:app --port 9001 > server.log 2>&1 &
SERVER_PID=$!
sleep 5
python3 test_epic2.py
TEST_EXIT=$?
kill $SERVER_PID
cat server.log
exit $TEST_EXIT
