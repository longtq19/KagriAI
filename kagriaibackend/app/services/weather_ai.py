import json
from typing import List, Dict, Any
from app.core.config import settings
import ollama

def _dedup(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for s in items:
        t = (s or "").strip()
        if not t:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out

def enrich(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    relevant = []
    for x in items:
        st = str(x.get("status", "") or "").upper()
        if st in ("UNDER_LIMIT", "UPPER_LIMIT"):
            relevant.append(x)
    
    plant = ""
    phase = ""
    for x in items:
        if not plant:
            plant = str(x.get("plant", "") or "")
        if not phase:
            phase = str(x.get("phaseName", x.get("phase", "") or "") or "")
        if plant and phase:
            break

    # Prepare seeds for fallback or context
    # We can try to classify here for fallback purposes, but for the prompt we pass everything
    
    instruction = (
        "Bạn là AI hỗ trợ ra quyết định nông nghiệp, tập trung vào cà phê Robusta khu vực Tây Nguyên (Việt Nam).\n\n"
        "ĐẦU VÀO:\n"
        "Bạn sẽ nhận một JSON chứa các chỉ số thời tiết và đất đai.\n"
        "Các chỉ số có thể có tên tiếng Anh hoặc tiếng Việt.\n\n"
        "NHIỆM VỤ:\n"
        "1. Phân loại các chỉ số vào 2 nhóm:\n"
        "   a. Nhóm \"weather\": \n"
        "      - Độ ẩm không khí (Air humidity), Cường độ ánh sáng, Thời gian chiếu sáng.\n"
        "      - Tốc độ gió, Hướng gió, Áp suất (Pressure), Lượng mưa, Sương mù.\n"
        "      - Air_temperature (Nhiệt độ không khí).\n"
        "   b. Nhóm \"soil\": \n"
        "      - Độ ẩm đất (Soil humidity), Nhiệt độ đất (Soil temperature).\n"
        "      - Độ dẫn điện, Độ pH (ph).\n"
        "      - Hàm lượng N, P, K (n, p, k).\n"
        "      - Các chỉ số mà cảnh báo nhắc đến 'rễ', 'đất' thường thuộc nhóm này.\n"
        "      - Lưu ý: 'temperature' nếu đi kèm cảnh báo về rễ -> Soil. 'humidity' nếu cảnh báo thối rễ -> Soil.\n\n"
        "2. Với các chỉ số có trạng thái UNDER_LIMIT hoặc UPPER_LIMIT (kể cả chỉ số hiếm như N, P, K):\n"
        "   - Tạo danh sách \"warnings\" (cảnh báo) giải thích tác động tiêu cực.\n"
        "   - Tạo danh sách \"recommendations\" (khuyến nghị) nêu biện pháp khắc phục.\n"
        "   - Nếu có warning mà không có recommendation (hoặc ngược lại) vẫn lấy thông tin.\n"
        "   - KHÔNG ĐƯỢC BỎ SÓT bất kỳ chỉ số nào có cảnh báo/khuyến nghị.\n\n"
        "QUY TẮC XUẤT (RẤT QUAN TRỌNG):\n"
        "- Chỉ trả về JSON hợp lệ.\n"
        "- KHÔNG giải thích, KHÔNG thêm text ngoài JSON, KHÔNG dùng markdown.\n"
        "- Mỗi mục (warning/recommendation) có \"id\" tăng dần từ 1 cho mỗi danh sách (reset về 1 cho mỗi nhóm weather/soil).\n"
        "- \"description\": mô tả khoa học, dễ hiểu, dễ thực hiện.\n"
        "- Ngôn ngữ: Tiếng Việt.\n\n"
        "ĐỊNH DẠNG JSON TRẢ VỀ (BẮT BUỘC):\n"
        "{\n"
        "  \"data\": {\n"
        "    \"weather\": {\n"
        "      \"warnings\": [ { \"id\": 1, \"description\": \"...\" } ],\n"
        "      \"recommendations\": [ { \"id\": 1, \"description\": \"...\" } ]\n"
        "    },\n"
        "    \"soil\": {\n"
        "      \"warnings\": [ { \"id\": 1, \"description\": \"...\" } ],\n"
        "      \"recommendations\": [ { \"id\": 1, \"description\": \"...\" } ]\n"
        "    }\n"
        "  }\n"
        "}\n"
    )

    context_lines = []
    if plant:
        context_lines.append(f"plant: {plant}")
    if phase:
        context_lines.append(f"phase: {phase}")
    
    # Pass all relevant items to LLM
    input_json = json.dumps({"items": relevant}, ensure_ascii=False)
    
    # We can also pass existing warnings/recommendations from items as hints if needed, 
    # but the user wants the AI to generate/refine. 
    # Let's extract them just in case to provide context if they exist.
    warnings_seed = _dedup([str(x.get("warning", "") or "") for x in relevant])
    recs_seed = _dedup([str(x.get("recomment", "") or "") for x in relevant])
    
    seed_w = "\n".join([f"- {w}" for w in warnings_seed]) if warnings_seed else ""
    seed_r = "\n".join([f"- {r}" for r in recs_seed]) if recs_seed else ""
    
    extra_seed = ""
    if seed_w or seed_r:
        extra_seed = f"\nGợi ý từ dữ liệu thô (tham khảo):\nCảnh báo: {seed_w}\nKhuyến nghị: {seed_r}\n"

    context_block = "\n".join(context_lines)
    prompt = (
        instruction
        + "\n"
        + context_block
        + "\n\nJSON_ĐẦU_VÀO:\n"
        + input_json
        + "\n"
        + extra_seed
        + "Chỉ trả về JSON hợp lệ:"
    )

    try:
        result = ollama.generate(
            model=settings.MODEL_NAME,
            prompt=prompt,
            stream=False,
            options={
                "temperature": settings.TEMPERATURE
            }
        )
        text = str(result.get("response", "") or "").strip()
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]
        
        # Clean markdown code blocks if present
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
            
        data = json.loads(text)
        
        # Validate structure and Re-index IDs to be safe
        if (isinstance(data, dict) and "data" in data and 
            "weather" in data["data"] and "soil" in data["data"]):
            
            # Helper to re-index
            def reindex(items):
                if not isinstance(items, list): return []
                return [{"id": i+1, "description": x.get("description", "")} for i, x in enumerate(items)]
            
            data["data"]["weather"]["warnings"] = reindex(data["data"]["weather"].get("warnings", []))
            data["data"]["weather"]["recommendations"] = reindex(data["data"]["weather"].get("recommendations", []))
            data["data"]["soil"]["warnings"] = reindex(data["data"]["soil"].get("warnings", []))
            data["data"]["soil"]["recommendations"] = reindex(data["data"]["soil"].get("recommendations", []))
            
            return data
            
    except Exception as e:
        print(f"Error calling LLM or parsing: {e}")
        pass

    # Fallback logic
    weather_keywords = [
        "Độ ẩm không khí", "Cường độ ánh sáng", "Thời gian chiếu sáng", 
        "Tốc độ gió", "Hướng gió", "Áp suất", "Lượng mưa", "Sương mù", "sương muối",
        "air_temperature", "pressure"
    ]
    # Note: 'humidity' is ambiguous, 'temperature' is ambiguous.
    
    soil_keywords = [
        "Độ ẩm đất", "Nhiệt độ đất", "Độ dẫn điện", "Độ pH", 
        "Hàm lượng N", "Hàm lượng P", "Hàm lượng K",
        "ph", "n", "p", "k", "ec"
    ]

    weather_warnings = []
    weather_recs = []
    soil_warnings = []
    soil_recs = []

    for x in relevant:
        topic = str(x.get("topic_name", x.get("topic", "") or "") or "").lower()
        warning = str(x.get("warning", "") or "")
        recomment = str(x.get("recomment", "") or "")
        
        # Heuristic classification
        is_weather = any(k.lower() in topic for k in weather_keywords)
        is_soil = any(k.lower() in topic for k in soil_keywords)
        
        # Special cases from user input
        if "temperature" in topic:
            if "air" in topic:
                is_weather = True
                is_soil = False
            else:
                # 'temperature' without 'air' -> likely soil if warning mentions roots
                if "rễ" in warning.lower() or "đất" in warning.lower():
                    is_soil = True
                    is_weather = False
                else:
                    # Default to weather if unknown? Or Soil?
                    # Given the example, 'temperature' -> Soil
                    is_soil = True 
                    
        if "humidity" in topic:
             # 'humidity' -> usually air, but if warning mentions roots -> soil
             if "rễ" in warning.lower() or "đất" in warning.lower() or "thối" in warning.lower():
                 is_soil = True
                 is_weather = False
             else:
                 is_weather = True

        target_w = None
        target_r = None
        
        if is_soil:
            target_w = soil_warnings
            target_r = soil_recs
        elif is_weather:
            target_w = weather_warnings
            target_r = weather_recs
        else:
            # Default to weather
            target_w = weather_warnings
            target_r = weather_recs

        if warning:
            target_w.append(warning)
        if recomment:
            target_r.append(recomment)

    # Dedup and format
    def to_objs(lst):
        return [{"id": i+1, "description": val} for i, val in enumerate(_dedup(lst))]

    return {
        "data": {
            "weather": {
                "warnings": to_objs(weather_warnings),
                "recommendations": to_objs(weather_recs)
            },
            "soil": {
                "warnings": to_objs(soil_warnings),
                "recommendations": to_objs(soil_recs)
            }
        }
    }
