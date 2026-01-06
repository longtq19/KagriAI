#!/usr/bin/env bash
set -e
echo "Starting High-Quality Vietnamese TTS Server (macOS/Linux)"
python3 -m pip install --upgrade pip
python3 -m pip install edge-tts fastapi uvicorn
python3 tts_server.py
