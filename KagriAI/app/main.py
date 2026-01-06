import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from app.api import websocket
from app.core.config import settings
from app.services.conversation import conversation_manager
from contextlib import asynccontextmanager

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

@app.get("/")
def health_check():
    return {"status": "ok", "service": "Kagri AI Server"}
