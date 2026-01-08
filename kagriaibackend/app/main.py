import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from app.api import chatws
from app.api import weatherpost
from app.core.config import settings
from app.core.database import init_db, init_chat_db, append_user_turn, update_ai_turn, update_user_image_path
from app.services.conversation import conversation_manager
from app.services.diagnosis import diagnosis_service
from app.services.time_service import time_service
from pydantic import BaseModel
from contextlib import asynccontextmanager
import os
import uuid
import base64
from typing import Optional

class DiagnosisRequest(BaseModel):
    image: str
    session_id: Optional[str] = None
    text: Optional[str] = None

class ConvertRequest(BaseModel):
    date: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_chat_db()
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

app.include_router(chatws.router)
app.include_router(weatherpost.router)

# Mount static images (point to kagriaibackend/data/images)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(BASE_DIR, "data", "images")
if os.path.exists(IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

@app.post("/api/diagnose/durian")
async def diagnose_durian(request: DiagnosisRequest):
    session_id = request.session_id
    turn_idx = None
    img_path_abs = None
    if session_id:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uploads_dir = os.path.join(base_dir, "app", "data", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        filename = f"{session_id}-{uuid.uuid4().hex}.png"
        img_path_abs = os.path.join(uploads_dir, filename)
        img_b64 = request.image
        if "," in img_b64:
            img_b64 = img_b64.split(",", 1)[1]
        with open(img_path_abs, "wb") as f:
            f.write(base64.b64decode(img_b64))
        turn_idx = append_user_turn(session_id, "[image] " + (request.text or ""), None, None)
        update_user_image_path(session_id, turn_idx, img_path_abs)
    result = diagnosis_service.predict(request.image, "durian")
    if session_id and turn_idx is not None:
        preds = result.get("predictions", [])
        if result.get("error"):
            text_reply = "Dạ, ảnh chưa hợp lệ hoặc mô hình chưa sẵn sàng ạ."
        elif not preds:
            text_reply = "Dạ, em chưa phát hiện được bệnh rõ ràng từ ảnh này. Anh/chị vui lòng thử ảnh khác rõ nét hơn ạ."
        else:
            top = preds[0]
            lines = []
            lines.append(f"Dạ, ảnh cho thấy khả năng cao: {top['name']} ({top['probability']}%).")
            if len(preds) > 1:
                lines.append("Các khả năng tiếp theo:")
                for p in preds[1:]:
                    lines.append(f"- {p['name']} ({p['probability']}%)")
            lines.append("Em gửi kèm ảnh mẫu bệnh để anh/chị đối chiếu ạ.")
            text_reply = "\n".join(lines)
        update_ai_turn(session_id, turn_idx, text_reply)
    return result

@app.post("/api/diagnose/coffee")
async def diagnose_coffee(request: DiagnosisRequest):
    session_id = request.session_id
    turn_idx = None
    img_path_abs = None
    if session_id:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uploads_dir = os.path.join(base_dir, "app", "data", "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        filename = f"{session_id}-{uuid.uuid4().hex}.png"
        img_path_abs = os.path.join(uploads_dir, filename)
        img_b64 = request.image
        if "," in img_b64:
            img_b64 = img_b64.split(",", 1)[1]
        with open(img_path_abs, "wb") as f:
            f.write(base64.b64decode(img_b64))
        turn_idx = append_user_turn(session_id, "[image] " + (request.text or ""), None, None)
        update_user_image_path(session_id, turn_idx, img_path_abs)
    result = diagnosis_service.predict(request.image, "coffee")
    if session_id and turn_idx is not None:
        preds = result.get("predictions", [])
        if result.get("error"):
            text_reply = "Dạ, ảnh chưa hợp lệ hoặc mô hình chưa sẵn sàng ạ."
        elif not preds:
            text_reply = "Dạ, em chưa phát hiện được bệnh rõ ràng từ ảnh này. Anh/chị vui lòng thử ảnh khác rõ nét hơn ạ."
        else:
            top = preds[0]
            lines = []
            lines.append(f"Dạ, ảnh cho thấy khả năng cao: {top['name']} ({top['probability']}%).")
            if len(preds) > 1:
                lines.append("Các khả năng tiếp theo:")
                for p in preds[1:]:
                    lines.append(f"- {p['name']} ({p['probability']}%)")
            lines.append("Em gửi kèm ảnh mẫu bệnh để anh/chị đối chiếu ạ.")
            text_reply = "\n".join(lines)
        update_ai_turn(session_id, turn_idx, text_reply)
    return result

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

@app.post("/api/kagriai/diagnose/durian")
async def diagnose_durian_kagriai(request: DiagnosisRequest):
    return await diagnose_durian(request)

@app.post("/api/kagriai/diagnose/coffee")
async def diagnose_coffee_kagriai(request: DiagnosisRequest):
    return await diagnose_coffee(request)

@app.post("/api/kagriai/convert/lunar-to-solar")
async def convert_lunar_to_solar_kagriai(req: ConvertRequest):
    return await convert_lunar_to_solar(req)

@app.post("/api/kagriai/convert/solar-to-lunar")
async def convert_solar_to_lunar_kagriai(req: ConvertRequest):
    return await convert_solar_to_lunar(req)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
 
