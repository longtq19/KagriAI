import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from starlette.websockets import WebSocketState
from app.services.llm_engine import llm_engine
from app.services.hybrid_search import hybrid_engine
from app.services.vision import vision_engine
from app.services.time_service import time_service
from app.services.market_price import market_price_service
from app.core.config import settings
from app.core.database import get_db_connection
import random
import re

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
        try:
            if websocket.client_state != WebSocketState.CONNECTED:
                return
            await websocket.send_json(message)
        except Exception as e:
            print(f"send_json error (ignored): {e}")

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
            print(f"[WS] Received: {data[:120]}")
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

            # --- CUSTOM HANDLER FOR TIME/DATE ---
            lower_data = data.lower().strip()
            time_keywords = ["mấy giờ", "ngày bao nhiêu", "hôm nay là", "thời gian", "ngày mấy", "giờ nào"]
            is_time_query = any(k in lower_data for k in time_keywords)
            
            nums = re.findall(r"\d{1,4}", lower_data)
            am_keywords = ["âm", "am"]
            duong_keywords = ["dương", "duong"]
            convert_keywords = ["chuyển", "chuyen", "đổi", "doi", "convert", "->", "sang", "bao nhiêu dương", "bao nhieu duong", "là ngày dương", "la ngay duong"]
            has_am = any(k in lower_data for k in am_keywords)
            has_duong = any(k in lower_data for k in duong_keywords)
            has_convert_kw = any(k in lower_data for k in convert_keywords)
            is_convert_intent = len(nums) >= 3 and (has_convert_kw or (has_am and has_duong))
            
            if is_convert_intent:
                try:
                    a, b, c = nums[0], nums[1], nums[2]
                    if len(a) == 4:
                        date_str = f"{a}/{b}/{c}"
                    else:
                        date_str = f"{a}/{b}/{c}"
                    convert_to_am = any(phrase in lower_data for phrase in ["sang âm", "doi sang am", "đổi sang âm", "duong sang am", "dương sang âm"])
                    convert_to_duong = any(phrase in lower_data for phrase in ["sang dương", "doi sang duong", "đổi sang dương", "am sang duong", "âm sang dương"])
                    idx_am = min([lower_data.find(k) for k in am_keywords if k in lower_data] + [9999])
                    idx_duong = min([lower_data.find(k) for k in duong_keywords if k in lower_data] + [9999])
                    if convert_to_duong and not convert_to_am:
                        is_lunar = True
                    elif convert_to_am and not convert_to_duong:
                        is_lunar = False
                    elif has_am and has_duong:
                        is_lunar = idx_am <= idx_duong
                    else:
                        is_lunar = has_am and not has_duong
                    result_text = time_service.convert_lunar_solar(date_str, is_lunar=is_lunar)
                    await manager.send_json({"type": "start"}, websocket)
                    await manager.send_json({"type": "stream", "content": result_text}, websocket)
                    await manager.send_json({"type": "end"}, websocket)
                    history_store[session_id]["turns"].append({"user": data, "ai": result_text})
                    if len(history_store[session_id]["turns"]) > settings.MAX_TURNS:
                        history_store[session_id]["turns"].pop(0)
                    continue
                except Exception as e:
                    await manager.send_json({"type": "start"}, websocket)
                    await manager.send_json({"type": "stream", "content": "Dạ, em không chuyển được ngày âm dương với định dạng vừa nhập ạ."}, websocket)
                    await manager.send_json({"type": "end"}, websocket)
                    history_store[session_id]["turns"].append({"user": data, "ai": "Không chuyển được ngày âm dương"})
                    if len(history_store[session_id]["turns"]) > settings.MAX_TURNS:
                        history_store[session_id]["turns"].pop(0)
                    continue
            
            if (not is_convert_intent) and is_time_query:
                try:
                    time_response = time_service.get_current_time_info()
                    await manager.send_json({"type": "start"}, websocket)
                    await manager.send_json({"type": "stream", "content": time_response}, websocket)
                    await manager.send_json({"type": "end"}, websocket)
                    
                    history_store[session_id]["turns"].append({"user": data, "ai": time_response})
                    if len(history_store[session_id]["turns"]) > settings.MAX_TURNS:
                        history_store[session_id]["turns"].pop(0)
                    continue
                except Exception as e:
                    print(f"Time service error: {e}")

            # --- CUSTOM HANDLER FOR DIAGNOSIS INTENT ---
            lower_data = data.lower().strip()
            diagnose_keywords = [
                "chẩn đoán", "chẩn đoán bệnh", "chẩn đoán bệnh cây trồng",
                "chẩn đoán qua ảnh", "chan doan", "chan doan benh", "chan doan qua anh"
            ]
            is_diagnose_intent = any(k in lower_data for k in diagnose_keywords)
            if is_diagnose_intent:
                try:
                    guide = (
                        "Để chẩn đoán bệnh cây trồng qua ảnh, mời anh/chị bấm nút "
                        "“Chẩn đoán bệnh cây trồng qua ảnh” ở cạnh ô nhập, tải ảnh vết bệnh lên và chọn loại cây.\n\n"
                        "Lưu ý:\n"
                        "- Hiện hỗ trợ: Sầu Riêng (Thán thư, Ung thư thân, Thối trái, Rệp sáp, Nấm hồng, Bồ hóng, Cháy lá chết ngọn, Xì mủ thân, Bọ trĩ, Vàng lá) và Cà Phê (Gỉ sắt, Sâu vẽ bùa, Bệnh khô cành, Khỏe mạnh).\n"
                        "- Ảnh cần rõ nét, tập trung vết bệnh, ánh sáng tốt, khoảng cách 30–50 cm.\n"
                        "- Nếu bệnh ngoài danh sách, kết quả có thể chưa chính xác. Liên hệ hotline 0985.562.582 hoặc kagri.vn để được tư vấn chuyên gia."
                    )
                    await manager.send_json({"type": "start"}, websocket)
                    chunk_size = 100
                    for i in range(0, len(guide), chunk_size):
                        await manager.send_json({"type": "stream", "content": guide[i:i+chunk_size]}, websocket)
                        await asyncio.sleep(0.02)
                    await manager.send_json({"type": "end"}, websocket)
                    
                    history_store[session_id]["turns"].append({"user": data, "ai": guide})
                    if len(history_store[session_id]["turns"]) > settings.MAX_TURNS:
                        history_store[session_id]["turns"].pop(0)
                    continue
                except Exception as e:
                    print(f"Diagnosis guide error: {e}")

            # --- CUSTOM HANDLER FOR MARKET PRICE ---
            lower_data = data.lower().strip()
            price_keywords = ["giá nông sản", "giá cà phê", "giá tiêu", "giá lúa", "giá gạo", "giá thóc", "giá sầu riêng", "giá heo", "giá lợn"]
            is_price_query = any(k in lower_data for k in price_keywords)
            
            if is_price_query:
                try:
                    # Detect product to show meaningful progress
                    product = "nông sản"
                    source_hint = "thị trường nội địa"
                    if "tiêu" in lower_data:
                        product = "hồ tiêu"
                        source_hint = "giatieu.com"
                    elif "cà phê" in lower_data or "cafe" in lower_data:
                        product = "cà phê"
                        source_hint = "baoquocte.vn"
                    elif "lúa" in lower_data or "gạo" in lower_data or "thóc" in lower_data:
                        product = "lúa gạo"
                        source_hint = "vietnambiz.vn"
                    elif "sầu riêng" in lower_data:
                        product = "sầu riêng"
                        source_hint = "nguồn tổng hợp"
                    
                    
                    await asyncio.sleep(0.05)
                    
                    
                    price_response = market_price_service.get_prices(lower_data)
                    
                    
                    await manager.send_json({"type": "start"}, websocket)
                    
                    chunk_size = 80
                    for i in range(0, len(price_response), chunk_size):
                        await manager.send_json({"type": "stream", "content": price_response[i:i+chunk_size]}, websocket)
                        await asyncio.sleep(0.02)
                    
                    await manager.send_json({"type": "end"}, websocket)
                    
                    history_store[session_id]["turns"].append({"user": data, "ai": price_response})
                    if len(history_store[session_id]["turns"]) > settings.MAX_TURNS:
                        history_store[session_id]["turns"].pop(0)
                    continue
                except Exception as e:
                    print(f"Market price error: {e}")

            # --- CUSTOM HANDLER FOR PRODUCT LIST ---
            lower_data = data.lower().strip()
            product_intent_keywords = ["các sản phẩm", "danh sách sản phẩm", "sản phẩm của công ty", "tất cả sản phẩm", "sản phẩm đang có"]
            is_product_list = any(k in lower_data for k in product_intent_keywords)
            
            # Additional heuristic: "sản phẩm" + "bao nhiêu" / "tổng số" / "liệt kê"
            if not is_product_list and "sản phẩm" in lower_data:
                if any(x in lower_data for x in ["bao nhiêu", "tổng số", "liệt kê", "giới thiệu", "nào", "gì"]):
                    is_product_list = True
            
            if is_product_list:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT code, name, usage, url FROM products")
                    all_products = cursor.fetchall()
                    conn.close()
                    
                    total_count = len(all_products)
                    
                    if total_count > 0:
                        examples = random.sample(all_products, min(3, total_count))
                        
                        response_text = f"Dạ, hiện tại KAGRI đang cung cấp tổng cộng **{total_count} sản phẩm** phục vụ đa dạng nhu cầu của bà con nông dân ạ.\n\n"
                        response_text += "Các sản phẩm của KAGRI bao gồm thuốc trừ sâu, thuốc trừ bệnh, phân bón và các chế phẩm sinh học, giúp bảo vệ cây trồng khỏi sâu bệnh hại và tăng năng suất.\n\n"
                        response_text += "Em xin phép giới thiệu 3 sản phẩm tiêu biểu với các công dụng khác nhau ạ:\n\n"
                        
                        for i, prod in enumerate(examples, 1):
                            usage_text = prod['usage'] if prod['usage'] else "Đang cập nhật công dụng"
                            usage_text = " ".join(usage_text.split())
                            if len(usage_text) > 150:
                                usage_text = usage_text[:147] + "..."
                                
                            response_text += f"{i}. **{prod['name']}** ({prod['code']})\n"
                            response_text += f"   - Công dụng: {usage_text}\n"
                            response_text += f"   👉 Chi tiết: {prod['url']}\n\n"
                            
                        response_text += "Mời anh/chị xem thêm danh sách đầy đủ tại website hoặc hỏi em về loại bệnh cụ thể để em tư vấn sản phẩm phù hợp nhất ạ."
                        
                        await manager.send_json({"type": "start"}, websocket)
                        chunk_size = 50
                        for i in range(0, len(response_text), chunk_size):
                            await manager.send_json({"type": "stream", "content": response_text[i:i+chunk_size]}, websocket)
                            await asyncio.sleep(0.02)
                        
                        await manager.send_json({"type": "end"}, websocket)
                        
                        history_store[session_id]["turns"].append({"user": data, "ai": response_text})
                        if len(history_store[session_id]["turns"]) > settings.MAX_TURNS:
                            history_store[session_id]["turns"].pop(0)
                            
                        continue
                except Exception as e:
                    print(f"Product list handler error: {e}")

            try:
                context_result = hybrid_engine.get_context(data, last_product_code=last_code)
                context_text = context_result["text"]
                found_code = context_result["product_code"]
            except Exception as e:
                print(f"Context error: {e}")
                await manager.send_json({"type": "error", "content": "Lỗi lấy ngữ cảnh: " + str(e)}, websocket)
                await manager.send_json({"type": "end"}, websocket)
                continue
            
            # Update last_product_code if new product found
            if found_code:
                 history_store[session_id]["meta"]["last_product_code"] = found_code
                 print(f"Session {session_id} updated last_product_code: {found_code}")
            
            # 2. Build Prompt with ChatML format (escape braces in context to avoid .format errors)
            try:
                safe_context = context_text.replace("{", "{{").replace("}", "}}")
                system_msg = SYSTEM_INSTRUCTION.format(context=safe_context)
            except Exception as e:
                print(f"SYSTEM_INSTRUCTION format error: {e}")
                system_msg = SYSTEM_INSTRUCTION.format(context="")  # Fallback empty context
            
            full_prompt = f"<|im_start|>system\n{system_msg}<|im_end|>\n"
            
            for turn in history_store[session_id]["turns"]:
                full_prompt += f"<|im_start|>user\n{turn['user']}<|im_end|>\n"
                full_prompt += f"<|im_start|>assistant\n{turn['ai']}<|im_end|>\n"
            
            full_prompt += f"<|im_start|>user\n{data}\n<|im_end|>\n"
            full_prompt += "<|im_start|>assistant\n"
            
            # 3. Stream Response
            
            await manager.send_json({"type": "start"}, websocket)
            
            full_response = ""
            try:
                async for chunk in llm_engine.generate_stream(full_prompt, max_tokens=1024):
                    if chunk["sentence"]:
                        await manager.send_json({
                            "type": "stream",
                            "content": chunk["sentence"]
                        }, websocket)
                        full_response += chunk["sentence"]
                await manager.send_json({"type": "end"}, websocket)
            except Exception as e:
                await manager.send_json({"type": "error", "content": "Lỗi phản hồi AI: " + str(e)}, websocket)
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
