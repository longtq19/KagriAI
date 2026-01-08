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
    warnings_seed = _dedup([str(x.get("warning", "") or "") for x in relevant])
    recs_seed = _dedup([str(x.get("recomment", "") or "") for x in relevant])
    instruction = (
        "Bạn là AI hỗ trợ ra quyết định nông nghiệp, tập trung vào cà phê Robusta khu vực Tây Nguyên (Việt Nam).\n\n"
        "ĐẦU VÀO:\n"
        "Bạn sẽ nhận một JSON chứa các chỉ số môi trường, đất và dinh dưỡng của cây cà phê.\n\n"
        "NHIỆM VỤ:\n"
        "1. Phân tích các chỉ số có trạng thái UNDER_LIMIT hoặc UPPER_LIMIT.\n"
        "2. Tạo HAI mảng:\n"
        "- \"warnings\" (cảnh báo)\n"
        "- \"recommendations\" (khuyến nghị)\n\n"
        "QUY TẮC XUẤT (RẤT QUAN TRỌNG):\n"
        "- Chỉ trả về JSON hợp lệ.\n"
        "- Không dùng markdown, không chú thích, không giải thích thêm.\n"
        "- Không lặp lại các trường đầu vào như topic, value, status, timestamp.\n"
        "- Mỗi phần tử phải có:\n"
        "- \"id\": số nguyên tăng dần bắt đầu từ 1\n"
        "- \"description\": mô tả khoa học, dễ hiểu, thực tiễn\n"
        "- Ngôn ngữ: Tiếng Việt.\n"
        "- Văn phong: khoa học, rõ ràng, hữu ích cho nông dân.\n"
        "- Warnings giải thích tác động tiêu cực lên sinh lý cây.\n"
        "- Recommendations nêu biện pháp khắc phục và lợi ích nông học.\n\n"
        "ĐỊNH DẠNG KẾT QUẢ (TUÂN THỦ NGHIÊM NGẶT):\n"
        "{\n"
        "  \"data\": {\n"
        "    \"warnings\": [\n"
        "      { \"id\": 1, \"description\": \"...\" }\n"
        "    ],\n"
        "    \"recommendations\": [\n"
        "      { \"id\": 1, \"description\": \"...\" }\n"
        "    ]\n"
        "  }\n"
        "}\n\n"
        "LƯU Ý:\n"
        "- Không tự bịa thêm chỉ số mới.\n"
        "- Chỉ dựa vào dữ liệu đầu vào để lập luận.\n"
        "- Nếu chỉ số không cần cảnh báo/khuyến nghị thì bỏ qua.\n"
    )
    context_lines = []
    if plant:
        context_lines.append(f"plant: {plant}")
    if phase:
        context_lines.append(f"phase: {phase}")
    input_json = json.dumps({"items": relevant}, ensure_ascii=False)
    seed_w = "\n".join([f"- {w}" for w in warnings_seed]) if warnings_seed else ""
    seed_r = "\n".join([f"- {r}" for r in recs_seed]) if recs_seed else ""
    extra_seed = ""
    if seed_w or seed_r:
        extra_seed = f"\nGợi ý cảnh báo ban đầu:\n{seed_w}\n\nGợi ý khuyến nghị ban đầu:\n{seed_r}\n"
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
        if text.startswith("```"):
            text = text.strip("` \n")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            warnings_out = data["data"].get("warnings")
            recommendations_out = data["data"].get("recommendations")
            if isinstance(warnings_out, list) and isinstance(recommendations_out, list):
                return {"data": {"warnings": warnings_out, "recommendations": recommendations_out}}
    except Exception:
        pass
    warnings_out = [{"id": i + 1, "description": w} for i, w in enumerate(warnings_seed) if w]
    recommendations_out = [{"id": i + 1, "description": r} for i, r in enumerate(recs_seed) if r]
    return {"data": {"warnings": warnings_out, "recommendations": recommendations_out}}
