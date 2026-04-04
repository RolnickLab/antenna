#!/bin/bash
set -e

# Forward signals to child process for graceful shutdown
trap 'kill -TERM $SERVER_PID 2>/dev/null' TERM INT

# Start FastAPI server in background
python /app/main.py &
SERVER_PID=$!

# Run registration if API key is configured (non-fatal)
if [ -n "$ANTENNA_API_KEY" ]; then
    python /app/register.py || echo "Registration failed, continuing in push-mode"
fi

# Wait for the server process
wait $SERVER_PID
