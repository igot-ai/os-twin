#!/bin/bash
for port in 6274 6275 6277; do
  pids=$(lsof -ti :"$port" 2>/dev/null)
  if [[ -n "$pids" ]]; then
    echo "Stopping processes on port $port: $pids"
    for pid in $pids; do
      # Verify the process still exists before signalling
      if kill -0 "$pid" 2>/dev/null; then
        kill -TERM "$pid" 2>/dev/null
      fi
    done
    # Wait up to 2 seconds for graceful shutdown
    sleep 2
    for pid in $pids; do
      if kill -0 "$pid" 2>/dev/null; then
        echo "  Force-killing PID $pid on port $port"
        kill -9 "$pid" 2>/dev/null
      fi
    done
  else
    echo "No process found on port $port"
  fi
done
