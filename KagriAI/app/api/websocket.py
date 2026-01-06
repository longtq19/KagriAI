import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from app.services.llm_engine import llm_engine
from app.services.hybrid_search import hybrid_engine
from app.services.vision import vision_engine
from app.core.config import settings

router = APIRouter()

# Store active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_json(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

manager = ConnectionManager()

# In-memory history for simplicity (or use DB/Redis later)
# Format: {session_id: [{"role": "user", "content": "..."}]}
history_store = {}

SYSTEM_INSTRUCTION = """Bạn là trợ lý AI chuyên nghiệp của công ty KAGRI (Công ty Cổ phần Tập đoàn Nông nghiệp KAGRI). 
Nhiệm vụ của bạn là hỗ trợ khách hàng trả lời các câu hỏi về sản phẩm nông nghiệp, phân bón, kỹ thuật trồng trọt và thông tin công ty.

QUY TẮC QUAN TRỌNG (BẮT BUỘC TUÂN THỦ):
1. NGÔN NGỮ: TUYỆT ĐỐI CHỈ DÙNG TIẾNG VIỆT.
2. PHONG CÁCH TRẢ LỜI:
   - Thân thiện, mềm mại, lễ phép, tận tâm.
   - Luôn dùng từ "Dạ" ở đầu câu và "ạ" ở cuối câu khi phù hợp để thể hiện sự tôn trọng (Ví dụ: "Dạ, số điện thoại của công ty là... ạ").
   - Tránh dùng từ ngữ quá chuyên môn gây khó hiểu, diễn đạt tự nhiên như người thật.
3. CHÍNH XÁC VÀ TRUNG THỰC (QUAN TRỌNG NHẤT):
   - Với câu hỏi về CÔNG TY, SẢN PHẨM, CHUYÊN GIA: CHỈ được sử dụng thông tin có trong phần "CONTEXT".
   - TUYỆT ĐỐI KHÔNG sử dụng kiến thức bên ngoài để trả lời về các chủ đề này.
   - Nếu Context KHÔNG chứa thông tin: Hãy trả lời "Dạ, hiện tại em chưa tìm thấy thông tin này trong hệ thống dữ liệu của KAGRI. Mời anh/chị liên hệ hotline 0985 562 582 để được hỗ trợ chi tiết ạ."
   - KHÔNG ĐƯỢC BỊA ĐẶT (Hallucinate) bất kỳ thông tin nào.
4. XỬ LÝ CÂU HỎI VỀ CÔNG TY:
   - Trình bày ĐẦY ĐỦ và CHI TIẾT thông tin từ Context (Tầm nhìn, Sứ mệnh, Giá trị cốt lõi...).
   - Với số điện thoại/địa chỉ: Trả lời chính xác kèm lời dẫn lịch sự.
5. Khi trả lời về thông tin CÔNG TY / SẢN PHẨM / CHUYÊN GIA: LUÔN kèm lời mời "Mời xem chi tiết tại: <URL>" sử dụng đúng URL có trong Context.
6. Với câu hỏi về SẢN PHẨM CỤ THỂ: Trả lời ĐẦY ĐỦ các trường (Tên, Thành phần, Công dụng, Hướng dẫn sử dụng) nếu có trong Context.

THÔNG TIN ĐƯỢC CUNG CẤP (CONTEXT):
{context}
"""

@router.websocket("/ws/kagri-ai")
async def websocket_endpoint(websocket: WebSocket, session_id: str = "default"):
    await manager.connect(websocket)
    
    # Init history if new session
    if session_id not in history_store:
        history_store[session_id] = {
            "turns": [],
            "meta": {"last_product_code": None} # Store metadata like last mentioned product
        }
    
    try:
        while True:
            data = await websocket.receive_text()
            parsed = None
            try:
                parsed = json.loads(data)
            except Exception:
                parsed = None
            
            # Ensure session exists in history_store
            if session_id not in history_store:
                history_store[session_id] = {
                    "turns": [],
                    "meta": {"last_product_code": None}
                }

            # 1. Get Context (Hybrid Search)
            # Retrieve last_product_code from session meta
            last_code = history_store[session_id]["meta"].get("last_product_code")
            
            if isinstance(parsed, dict) and parsed.get("type") == "image_query" and parsed.get("image_base64"):
                try:
                    disease_name = vision_engine.predict(parsed.get("image_base64"))
                    text_reply = (
                        f"Cây của bạn đang bị {disease_name}. "
                        "Hiện tại KAGRI AI chưa được đào tạo chuyên sâu về phòng và chữa bệnh. "
                        "Vui lòng liên hệ công ty theo số điện thoại 0985 562 582 để được hướng dẫn hoặc truy cập website https://kagri.vn"
                    )
                    await manager.send_json({"type": "start"}, websocket)
                    await manager.send_json({"type": "stream", "content": text_reply}, websocket)
                    await manager.send_json({"type": "end"}, websocket)
                    history_store[session_id]["turns"].append({"user": parsed.get("text", ""), "ai": text_reply})
                    if len(history_store[session_id]["turns"]) > settings.MAX_TURNS:
                        history_store[session_id]["turns"].pop(0)
                except Exception as e:
                    print(f"Vision error: {e}")
                    await manager.send_json({"type": "error", "content": "Lỗi xử lý ảnh: " + str(e)}, websocket)
                continue
            context_result = hybrid_engine.get_context(data, last_product_code=last_code)
            context_text = context_result["text"]
            found_code = context_result["product_code"]
            
            # Update last_product_code if new product found
            if found_code:
                 history_store[session_id]["meta"]["last_product_code"] = found_code
                 print(f"Session {session_id} updated last_product_code: {found_code}")
            
            # 2. Build Prompt with ChatML format
            system_msg = SYSTEM_INSTRUCTION.format(context=context_text)
            
            full_prompt = f"<|im_start|>system\n{system_msg}<|im_end|>\n"
            
            for turn in history_store[session_id]["turns"]:
                full_prompt += f"<|im_start|>user\n{turn['user']}<|im_end|>\n"
                full_prompt += f"<|im_start|>assistant\n{turn['ai']}<|im_end|>\n"
            
            full_prompt += f"<|im_start|>user\n{data}\n<|im_end|>\n"
            full_prompt += "<|im_start|>assistant\n"
            
            # 3. Stream Response
            await manager.send_json({"type": "start"}, websocket)
            
            full_response = ""
            async for chunk in llm_engine.generate_stream(full_prompt, max_tokens=1024):
                if chunk["sentence"]:
                    await manager.send_json({
                        "type": "stream",
                        "content": chunk["sentence"]
                    }, websocket)
                    full_response += chunk["sentence"]
                
                if chunk["is_final"]:
                    pass
            
            await manager.send_json({"type": "end"}, websocket)
            
            # 4. Save to History
            history_store[session_id]["turns"].append({"user": data, "ai": full_response})
            if len(history_store[session_id]["turns"]) > settings.MAX_TURNS:
                history_store[session_id]["turns"].pop(0)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # Optional: Clean up history after timeout? For now keep it simple. 
        if session_id in history_store:
            del history_store[session_id]   
