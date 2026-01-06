import os
import sys
from typing import AsyncGenerator, Optional
from app.core.config import settings
from app.utils.text_processing import SentenceBuffer
import ollama
import json

class LLMEngine:
    def __init__(self):
        self.model_name = "qwen2.5:7b"
        self.client = ollama.AsyncClient()
        self.model = True # Assume true, check later or let it fail gracefully

    async def generate_stream(self, prompt: str, max_tokens: int = 4096) -> AsyncGenerator[dict, None]:
        """
        Generates response and yields sentences using Ollama Async.
        """
        buffer = SentenceBuffer()
        
        try:
            # Stream from Ollama Async
            stream = await self.client.generate(
                model=self.model_name,
                prompt=prompt,
                stream=True,
                options={
                    "num_ctx": settings.N_CTX,
                    "temperature": settings.TEMPERATURE,
                    "num_predict": max_tokens,
                    "stop": ["<|im_end|>", "<|im_start|>", "User:", "\nUser"]
                },
                raw=True
            )

            async for output in stream:
                token = output.get("response", "")
                if not token:
                    continue
                sentences = buffer.add_token(token)
                for sentence in sentences:
                    yield {
                        "sentence": sentence,
                        "is_final": False
                    }
            
            # Flush remaining buffer
            final_sentence = buffer.flush()
            if final_sentence:
                yield {
                    "sentence": final_sentence,
                    "is_final": False
                }
            
            # Signal completion
            yield {
                "sentence": "",
                "is_final": True
            }
        except Exception as e:
            print(f"Ollama Error: {e}")
            yield {
                "sentence": f"Lỗi khi gọi AI: {str(e)}",
                "is_final": True
            }

    def check_relevance(self, text: str) -> bool:
        """
        Check disabled: Always return True to allow all topics.
        """
        return True
    
    def classify_intent(self, query: str) -> dict:
        """
        Use LLM to classify whether to search DB, RAG, or both.
        Returns a dict: {"intent": "db_company"|"db_product"|"rag"|"mixed", "target_field": optional}
        """
        instruction = (
            "Bạn là bộ phân loại truy vấn cho hệ thống tìm kiếm lai (DB + RAG). "
            "Phân loại câu hỏi dưới đây vào một trong các nhóm sau và trả về JSON:\n"
            "- db_company: hỏi thông tin công ty (địa chỉ, hotline, email, website, giới thiệu)\n"
            "- db_product: hỏi dữ kiện sản phẩm có cấu trúc (thành phần, liều lượng, mã, url, danh mục)\n"
            "- rag: hỏi mô tả/công dụng/lợi ích/lưu ý chung cần RAG\n"
            "- mixed: vừa cần dữ kiện (db_product) vừa cần mô tả (rag)\n\n"
            "Nếu db_product, hãy suy ra 'target_field' trong [ingredients, usage, code, url, category] nếu phù hợp, nếu không thì để null.\n"
            "CHỈ TRẢ VỀ JSON hợp lệ với các khóa: intent, target_field."
        )
        prompt = f"<|im_start|>system\n{instruction}<|im_end|>\n<|im_start|>user\n{query}\n<|im_end|>\n<|im_start|>assistant\n"
        try:
            result = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                stream=False,
                options={
                    "temperature": settings.TEMPERATURE,
                    "stop": ["<|im_end|>"]
                }
            )
            text = result.get("response", "").strip()
            
            # Extract JSON block if present
            if "{" in text and "}" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]

            # Try parse JSON from the response
            # Some models may wrap JSON in code fences; strip them
            if text.startswith("```"):
                text = text.strip("` \n")
                # after stripping backticks, there might be "json\n"
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            data = json.loads(text)
            intent = data.get("intent", "rag")
            target_field = data.get("target_field")
            return {"intent": intent, "target_field": target_field}
        except Exception as e:
            print(f"LLM classify_intent error: {e}")
            # Fallback simple heuristic
            q = query.lower()
            company_keywords = ["địa chỉ", "hotline", "số điện thoại", "sđt", "email", "liên hệ", "công ty", "ở đâu", "giấy phép", "mst", "mã số thuế", "nhà máy", "slogan", "tầm nhìn", "sứ mệnh"]
            if any(kw in q for kw in company_keywords):
                return {"intent": "db_company", "target_field": None}
            db_keywords = {
                "ingredients": ["thành phần", "chứa gì", "chất gì", "hàm lượng"],
                "usage": ["liều lượng", "cách dùng", "hướng dẫn sử dụng", "sử dụng thế nào", "pha như thế nào", "tưới bao nhiêu"],
                "code": ["mã sản phẩm", "sku", "mã số"],
                "url": ["link", "đường dẫn", "website", "trang web"],
                "category": ["loại gì", "nhóm nào", "danh mục"]
            }
            for field, keywords in db_keywords.items():
                if any(kw in q for kw in keywords):
                    return {"intent": "db_product", "target_field": field}
            rag_keywords = ["công dụng", "tác dụng", "lợi ích", "mô tả", "là gì", "an toàn", "lưu ý", "độc hại", "có tốt không"]
            if any(kw in q for kw in rag_keywords):
                return {"intent": "rag", "target_field": None}
            return {"intent": "rag", "target_field": None}

llm_engine = LLMEngine()
