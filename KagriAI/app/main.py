import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from app.api import websocket
from app.core.config import settings
from app.services.conversation import conversation_manager
from app.services.diagnosis import diagnosis_service
from app.services.time_service import time_service
from pydantic import BaseModel
from contextlib import asynccontextmanager

class DiagnosisRequest(BaseModel):
    image: str

class ConvertRequest(BaseModel):
    date: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create background task for cleanup
    task = asyncio.create_task(cleanup_loop())
    yield
    # Shutdown
    task.cancel()

async def cleanup_loop():
    while True:
        try:
            conversation_manager.cleanup()
            await asyncio.sleep(60) # Check every minute
        except asyncio.CancelledError:
            break

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(websocket.router)

# Mount static images
if os.path.exists("data/images"):
    app.mount("/images", StaticFiles(directory="data/images"), name="images")

@app.post("/api/diagnose/durian")
async def diagnose_durian(request: DiagnosisRequest):
    return diagnosis_service.predict(request.image, "durian")

@app.post("/api/diagnose/coffee")
async def diagnose_coffee(request: DiagnosisRequest):
    return diagnosis_service.predict(request.image, "coffee")

@app.get("/")
def health_check():
    return {"status": "ok", "service": "Kagri AI Server"}

@app.post("/api/convert/lunar-to-solar")
async def convert_lunar_to_solar(req: ConvertRequest):
    text = time_service.convert_lunar_solar(req.date, is_lunar=True)
    return {"result": text, "type": "lunar_to_solar"}

@app.post("/api/convert/solar-to-lunar")
async def convert_solar_to_lunar(req: ConvertRequest):
    text = time_service.convert_lunar_solar(req.date, is_lunar=False)
    return {"result": text, "type": "solar_to_lunar"}
