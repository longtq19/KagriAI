import sqlite3
import re
from app.core.database import get_db_connection
from app.services.rag_engine import rag_engine
from app.services.llm_engine import llm_engine

class HybridSearchEngine:
    def __init__(self):
        self.conn = None # Connection per request usually, but for simplicity here
        
    def get_db(self):
        return get_db_connection()

    def analyze_intent(self, query: str) -> dict:
        """
        Dùng LLM để xác định ý định: DB, RAG, hoặc cả hai.
        Fallback sang heuristic nếu LLM lỗi.
        """
        result = llm_engine.classify_intent(query)
        intent = result.get("intent", "rag")
        target_field = result.get("target_field")
        return {"intent": intent, "target_field": target_field}

    def search_db_product(self, query: str, code: str = None):
        """
        Fuzzy search product in DB.
        """
        conn = self.get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT code, name, url, ingredients, usage, category FROM products")
        products = cursor.fetchall()
        conn.close()
        
        # Exact code match
        if code:
            for p in products:
                if p['code'] == code:
                    return p
        
        best_match = None
        max_score = 0
        
        query_words = set(query.lower().split())
        
        for p in products:
            # Score based on overlap
            name_words = set(p['name'].lower().split())
            p_code = p['code'].lower()
            
            score = 0
            if p_code in query.lower():
                score += 10 # High priority for code match
            
            overlap = len(query_words.intersection(name_words))
            score += overlap
            
            if score > max_score and score > 0:
                max_score = score
                best_match = p
                
        return best_match

    def search_db_company(self):
        conn = self.get_db()
        row = conn.execute("SELECT * FROM company_info LIMIT 1").fetchone()
        conn.close()
        return row

    def search_db_experts(self, query: str = None):
        """
        Fetch experts from DB.
        If query contains specific name, filter by it.
        Otherwise return all (or top few).
        """
        conn = self.get_db()
        cursor = conn.cursor()
        
        # Simple heuristic to extract name from query if possible, 
        # but for now, let's just fetch all and filter in Python or use LIKE in SQL if simple.
        # Given the small number of experts, fetching all is fine.
        cursor.execute("SELECT name, title, degree, bio, profile_url FROM experts")
        experts = cursor.fetchall()
        conn.close()
        
        if not query:
            return experts[:2] # Return first 2 if no specific query
            
        # Filter by name if mentioned in query
        query_lower = query.lower()
        matched_experts = []
        for exp in experts:
            if exp['name'].lower() in query_lower:
                matched_experts.append(exp)
                
        if matched_experts:
            return matched_experts
            
        # If asking about experts generally but no name match found, return top 2
        if "chuyên gia" in query_lower or "bác sĩ" in query_lower:
            return experts[:2]
            
        return []

    def search_db_products_random(self, limit: int = 2):
        """
        Fetch random products for consultation.
        """
        conn = self.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT code, name, url, ingredients, usage, category FROM products ORDER BY RANDOM() LIMIT ?", (limit,))
        products = cursor.fetchall()
        conn.close()
        return products

    def get_context(self, query: str, last_product_code: str = None):
        analysis = self.analyze_intent(query)
        intent = analysis["intent"]
        context_parts = []
        
        print(f"DEBUG: Query='{query}', Intent='{intent}', LastProduct='{last_product_code}'")
        
        # Pre-fetch company info for fallback (hotline/website)
        comp_info = self.search_db_company()
        hotline = comp_info['hotline'] if comp_info and comp_info['hotline'] else "0985.562.582"
        website = comp_info['website'] if comp_info and comp_info['website'] else "https://kagri.vn/"
        
        fallback_msg = f"Xin lỗi bạn, hiện tại KAGRI AI chưa tìm thấy thông tin này trong hệ thống dữ liệu. Bạn vui lòng ghé thăm website {website} hoặc liên hệ hotline {hotline} để được hỗ trợ nhanh nhất."

        # Detect special keywords
        is_asking_expert = "chuyên gia" in query.lower() or "bác sĩ" in query.lower()
        is_asking_consultation = "tư vấn" in query.lower() and "sản phẩm" in query.lower()
        
        # Enhanced company keywords detection
        company_keywords = ["địa chỉ", "hotline", "số điện thoại", "sdt", "liên hệ", "công ty", "ở đâu", "website", "email", "trụ sở", "văn phòng"]
        is_asking_company = any(kw in query.lower() for kw in company_keywords)

        # 1. Company Info
        if intent == "db_company" or "kagri" in query.lower() or is_asking_expert or is_asking_company:
            if comp_info:
                qlower = query.lower()
                name = comp_info['name'] if comp_info['name'] else "KAGRI"
                hl = comp_info['hotline'] if comp_info['hotline'] else "Đang cập nhật"
                addr = comp_info['address'] if comp_info['address'] else "Đang cập nhật"
                em = comp_info['email'] if comp_info['email'] else "Đang cập nhật"
                web = comp_info['website'] if comp_info['website'] else "https://kagri.vn/"
                intro = comp_info['introduction'] if comp_info['introduction'] else ""
                vision = comp_info['vision'] if 'vision' in comp_info.keys() and comp_info['vision'] else ""
                mission = comp_info['mission'] if 'mission' in comp_info.keys() and comp_info['mission'] else ""
                core_values = comp_info['core_values'] if 'core_values' in comp_info.keys() and comp_info['core_values'] else ""
                slogan = comp_info['slogan'] if 'slogan' in comp_info.keys() and comp_info['slogan'] else ""
                factories = comp_info['factories'] if 'factories' in comp_info.keys() and comp_info['factories'] else ""
                license_tax = comp_info['license_tax'] if 'license_tax' in comp_info.keys() and comp_info['license_tax'] else ""
                
                info = f"DỮ LIỆU CÔNG TY:\n- Tên: {name}\n- Hotline: {hl}\n- Địa chỉ: {addr}\n- Email: {em}\n- Website: {web}\n- Slogan: {slogan}\n- Giới thiệu: {intro}\n- Tầm nhìn: {vision}\n- Sứ mệnh: {mission}\n- Giá trị cốt lõi: {core_values}\n- Nhà máy: {factories}\n- Giấy phép/MST: {license_tax}\nMời xem chi tiết tại: {web}\n"
                context_parts.append(info)
                
            # Special Logic: Experts
            if is_asking_expert:
                # Pass query to filter by name if exists
                experts = self.search_db_experts(query)
                if experts:
                    expert_text = "\nCác sản phẩm của KAGRI được nghiên cứu phát triển bởi đội ngũ các nhà khoa học đầu ngành cùng với các chuyên gia xuất sắc đến từ Học viện Nông nghiệp Việt Nam và Bộ Nông nghiệp & PTNT.\n"
                    expert_text += "DANH SÁCH CHUYÊN GIA (Sử dụng thông tin dưới đây):\n"
                    for idx, exp in enumerate(experts, 1):
                        expert_text += f"{idx}. {exp['degree']} {exp['name']} ({exp['title']})\n"
                        if exp['bio']: expert_text += f"   - Tiểu sử: {exp['bio']}\n"
                        if exp['profile_url']: expert_text += f"   - Xem chi tiết: {exp['profile_url']}\n"
                    context_parts.append(expert_text)
                else:
                    # Found no experts matching the name or query
                    context_parts.append("\nKHÔNG TÌM THẤY CHUYÊN GIA NÀO TRONG HỆ THỐNG TRÙNG KHỚP VỚI CÂU HỎI.\n")

            # Only fallback if we really intended to find company info but found nothing
            if intent == "db_company" and not context_parts:
                 return {"text": fallback_msg, "product_code": None}

        # 2. Product Info
        product_found = False
        product_db_info = ""
        found_product_code = None
        
        if is_asking_consultation:
            # Randomly pick 2 products to suggest
            suggested_products = self.search_db_products_random(limit=2)
            if suggested_products:
                suggestion_text = "\nGỢI Ý SẢN PHẨM TIÊU BIỂU (Tư vấn):\n"
                for p in suggested_products:
                    suggestion_text += f"- Sản phẩm: {p['name']} (Mã: {p['code']})\n"
                    suggestion_text += f"  Công dụng/Cách dùng: {p['usage']}\n"
                    suggestion_text += f"  Thành phần: {p['ingredients']}\n"
                    suggestion_text += f"  Link chi tiết: {p['url']}\n"
                    suggestion_text += f"  Mời xem chi tiết tại: {p['url']}\n"
                    suggestion_text += f"  Hoặc liên hệ hotline: {hotline}\n"
                context_parts.append(suggestion_text)
                product_found = True # Treat as found so we don't fallback

        if (intent in ["db_product", "mixed"] or "sản phẩm" in query.lower()) and not is_asking_consultation:
            product = self.search_db_product(query)
            # Context fallback: If no product found but we have last_product_code, use it regardless of intent
            if not product and last_product_code:
                 print(f"DEBUG: Using context product: {last_product_code}")
                 product = self.search_db_product(query, code=last_product_code)
            
            if product:
                product_found = True
                found_product_code = product['code']
                product_db_info = f"""
                DỮ LIỆU SẢN PHẨM:
                - Tên: {product['name']}
                - Mã: {product['code']}
                - URL: {product['url']}
                - Thành phần: {product['ingredients']}
                - Hướng dẫn sử dụng/Liều lượng: {product['usage']}
                - Loại/Danh mục: {product['category']}
                Mời xem chi tiết tại: {product['url']}
                Hoặc liên hệ hotline: {hotline}
                """
                context_parts.append(product_db_info)
            else:
                 print("DEBUG: No product match in DB")

        # 3. RAG / Fallback Logic
        
        # If intent is strictly DB product and we didn't find it -> Fail immediately
        if intent == "db_product" and not product_found and not context_parts:
             return {"text": fallback_msg, "product_code": None}

        # If intent allows RAG (mixed/rag), try RAG
        if intent in ["rag", "mixed"]:
            rag_docs = rag_engine.search(query, k=3)
            if rag_docs:
                rag_text = "\n".join(rag_docs)
                context_parts.append(f"Thông tin bổ sung (Mô tả, công dụng, lưu ý):\n{rag_text}")

        if not context_parts:
            # If strictly DB intent and failed -> Fallback
            if intent in ["db_company", "db_product"]:
                 return {"text": fallback_msg, "product_code": None}
            
            # If RAG/Mixed but nothing found -> Return empty string to let LLM handle chitchat
            return {"text": "", "product_code": None}

        return {"text": "\n".join(context_parts), "product_code": found_product_code}

hybrid_engine = HybridSearchEngine()
