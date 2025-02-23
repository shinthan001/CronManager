#!/bin/bash

# Activate the virtual environment
source venv_linux/bin/activate

# Run the FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 9090 --log-level info &> ./runtime.log&

# Get the FastAPI server process ID and save it to a file
echo $! > server.pid