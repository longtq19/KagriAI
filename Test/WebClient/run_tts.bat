@echo off
echo ===================================================
echo   STARTING HIGH-QUALITY VIETNAMESE TTS SERVER
echo   (Using Edge-TTS - Free & Natural)
echo ===================================================
echo.
echo Installing dependencies...
pip install edge-tts fastapi uvicorn
echo.
echo Starting TTS Server...
echo API available at: http://localhost:5050
echo.
python tts_server.py

pause
