#!/bin/bash
set -e

# Start FastAPI server in background
python /app/main.py &
SERVER_PID=$!

# Run registration if API key is configured
if [ -n "$ANTENNA_API_KEY" ]; then
    python /app/register.py
fi

# Wait for the server process
wait $SERVER_PID
