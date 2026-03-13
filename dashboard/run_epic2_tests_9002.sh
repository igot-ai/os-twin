#!/bin/bash
export PYTHONPATH=$PYTHONPATH:.
uvicorn api:app --port 9002 > server_test.log 2>&1 &
SERVER_PID=$!
sleep 5
# Update test_epic2.py or use a modified version to point to 9002
sed 's/9001/9002/g' test_epic2.py > test_epic2_tmp.py
python3 test_epic2_tmp.py
TEST_EXIT=$?
kill $SERVER_PID
cat server_test.log
rm test_epic2_tmp.py
exit $TEST_EXIT
