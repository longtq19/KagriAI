import os
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
import uuid
import io

app = FastAPI()

# Enable CORS to allow requests from the Web Client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Vietnamese Voice Configuration
# Options: vi-VN-NamMinhNeural (Male), vi-VN-HoaiMyNeural (Female)
VOICE = os.getenv("TTS_VOICE", "vi-VN-NamMinhNeural")

@app.get("/")
def home():
    return {
        "status": "TTS Server is running", 
        "voice": VOICE,
        "docs_url": "http://localhost:5050/docs"
    }

@app.post("/tts")
async def generate_speech(data: dict):
    """
    Generate speech from text using Edge-TTS (Microsoft Azure Cognitive Services - Free Tier)
    Streams audio directly to memory to avoid disk I/O and file conflicts.
    """
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        # Stream audio to memory
        communicate = edge_tts.Communicate(text, VOICE)
        mp3_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_data += chunk["data"]
        
        # Return the audio bytes directly
        return Response(content=mp3_data, media_type="audio/mpeg")

    except Exception as e:
        print(f"Error generating TTS: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"Starting TTS Server on port 5500...")
    print(f"Selected Voice: {VOICE}")
    # Run server
    uvicorn.run(app, host="0.0.0.0", port=5500)
