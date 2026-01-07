import requests
from bs4 import BeautifulSoup
import random
import datetime

class MarketPriceService:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_prices(self, query: str) -> str:
        query = query.lower()
        
        # 1. Determine product type
        product_type = "general"
        if "cà phê" in query or "cafe" in query:
            product_type = "coffee"
        elif "tiêu" in query:
            product_type = "pepper"
        elif "lúa" in query or "gạo" in query or "thóc" in query:
            product_type = "rice"
        elif "sầu riêng" in query:
            product_type = "durian"
        elif "heo" in query or "lợn" in query:
            product_type = "pork"

        # 2. Fetch data
        data = []
        source_note = ""

        if product_type == "pepper":
            data, source = self._get_pepper_prices()
            source_note = source
        elif product_type == "coffee":
            # Realtime from news/tag page
            data, source = self._get_coffee_prices_rt()
            source_note = source
        elif product_type == "durian":
            data, source = self._get_durian_prices_mock()
            source_note = source
        elif product_type == "rice":
            # Realtime from category page
            data, source = self._get_rice_prices_rt()
            source_note = source
        else:
            # General or other -> return a summary of available data
            p_data, p_source = self._get_pepper_prices()
            c_data, c_source = self._get_coffee_prices_rt()
            r_data, r_source = self._get_rice_prices_rt()
            
            response = "Dạ, em xin gửi thông tin giá nông sản hôm nay ạ:\n\n"
            if p_data:
                response += f"**Giá Tiêu ({p_source})**:\n{self._format_table(p_data)}\n"
            if c_data:
                response += f"**Giá Cà Phê ({c_source})**:\n{self._format_table(c_data)}\n"
            if r_data:
                response += f"**Giá Lúa ({r_source})**:\n{self._format_table(r_data)}\n"
            
            response += "\n*Lưu ý: Giá cả có thể thay đổi tùy theo thời điểm và địa phương.*"
            return response

        # 3. Format response for specific product
        if not data:
            return f"Dạ, hiện tại em chưa cập nhật được dữ liệu giá {product_type}. Anh/chị vui lòng thử lại sau ạ."
        
        product_name_map = {
            "pepper": "Hồ Tiêu",
            "coffee": "Cà Phê",
            "durian": "Sầu Riêng",
            "rice": "Lúa Gạo",
            "pork": "Heo Hơi"
        }
        p_name = product_name_map.get(product_type, "Nông Sản")
        
        response = f"Dạ, bảng giá **{p_name}** hôm nay ({source_note}):\n\n"
        response += self._format_table(data)
        response += "\n*Giá mang tính chất tham khảo, cập nhật từ thị trường.*"
        return response

    def _format_table(self, data: list) -> str:
        # data is list of dict: {loc: str, price: str, change: str}
        # Markdown table
        if not data:
            return ""
        
        # Find max length for padding (simple approach)
        table = "| Địa phương | Giá (VNĐ/kg) | Thay đổi |\n"
        table += "|---|---|---|\n"
        for item in data:
            change = item.get('change', '-')
            table += f"| {item['loc']} | {item['price']} | {change} |\n"
        return table

    def _get_pepper_prices(self):
        url = "https://giatieu.com/"
        try:
            resp = requests.get(url, headers=self.headers, timeout=5)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Analyze structure based on previous curl
                # <div class="home-gia"> ... <div class="h-min-max-gia">
                # Actually, giatieu.com often has a table #tablepress-1 or similar
                # Let's try to find text patterns if table parsing is hard
                
                # Fallback: Look for specific class "home-gia" blocks
                # <div class="min-max-value"><span class="h-mm--name">Đắk Lắk</span></div>
                # <div class="min-max-price"><span class="h-mm--gia">152,500 ₫</span></div>
                
                items = []
                # Looking for regions
                regions = ["Đắk Lắk", "Gia Lai", "Đắk Nông", "Bà Rịa", "Bình Phước", "Đồng Nai"]
                
                # Parsing logic specific to giatieu.com's current layout
                # It uses <div class="h-min-max-gia"> for summary, but usually has a full table below
                # Let's try to find the summary items first as they are prominent
                
                blocks = soup.select(".h-min-max-gia")
                for block in blocks:
                    name_tag = block.select_one(".h-mm--name")
                    price_tag = block.select_one(".h-mm--gia")
                    change_tag = block.select_one(".price_change")
                    
                    if name_tag and price_tag:
                        name = name_tag.get_text(strip=True)
                        price = price_tag.get_text(strip=True).replace('₫', '').strip()
                        change = change_tag.get_text(strip=True) if change_tag else "-"
                        items.append({"loc": name, "price": price, "change": change})
                
                if items:
                    return items, "Nguồn: giatieu.com"
                    
        except Exception as e:
            print(f"Error scraping pepper: {e}")
        
        return self._get_pepper_prices_mock()

    def _get_pepper_prices_mock(self):
        # Fallback data
        base = 152000
        return [
            {"loc": "Đắk Lắk", "price": f"{base:,}", "change": "+500"},
            {"loc": "Gia Lai", "price": f"{base-1000:,}", "change": "0"},
            {"loc": "Đắk Nông", "price": f"{base:,}", "change": "+500"},
            {"loc": "Bà Rịa - Vũng Tàu", "price": f"{base+1000:,}", "change": "+1000"},
            {"loc": "Bình Phước", "price": f"{base-500:,}", "change": "0"},
            {"loc": "Đồng Nai", "price": f"{base-1000:,}", "change": "-500"},
        ], "Dữ liệu tham khảo (Mô phỏng)"

    def _get_coffee_prices_mock(self):
        # Real-time scraping is blocked, use realistic mock
        base = 105000
        variation = random.randint(-500, 500)
        base += variation
        
        return [
            {"loc": "Đắk Lắk", "price": f"{base:,}", "change": "+200"},
            {"loc": "Lâm Đồng", "price": f"{base-800:,}", "change": "0"},
            {"loc": "Gia Lai", "price": f"{base-200:,}", "change": "+200"},
            {"loc": "Đắk Nông", "price": f"{base:,}", "change": "+200"},
            {"loc": "Hồ Chí Minh (Cảng)", "price": f"{base+3000:,}", "change": "+500"},
        ], "Dữ liệu tham khảo (Mô phỏng)"

    def _get_durian_prices_mock(self):
        # Durian Monthong / Ri6
        return [
            {"loc": "Tiền Giang (Ri6)", "price": "110,000 - 130,000", "change": "-"},
            {"loc": "Tiền Giang (Monthong)", "price": "140,000 - 160,000", "change": "-"},
            {"loc": "Đắk Lắk (Ri6)", "price": "100,000 - 120,000", "change": "-"},
            {"loc": "Đắk Lắk (Monthong)", "price": "130,000 - 150,000", "change": "-"},
        ], "Dữ liệu tham khảo (Mô phỏng)"

    def _get_rice_prices_mock(self):
        # Giá lúa tươi nội địa (tham khảo các tỉnh ĐBSCL)
        base = 8300
        return [
            {"loc": "An Giang", "price": f"{base:,}", "change": "+50"},
            {"loc": "Đồng Tháp", "price": f"{base+100:,}", "change": "+100"},
            {"loc": "Long An", "price": f"{base-50:,}", "change": "0"},
            {"loc": "Kiên Giang", "price": f"{base+150:,}", "change": "+50"},
            {"loc": "Vĩnh Long", "price": f"{base-100:,}", "change": "-50"},
        ], "Dữ liệu tham khảo (Mô phỏng, VNĐ/kg)"

    # --- Realtime helpers ---
    def _clean_text(self, html):
        try:
            soup = BeautifulSoup(html, 'html.parser')
            # Remove scripts/styles
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text("\n", strip=True)
            return text
        except Exception:
            return html

    def _find_numbers(self, s):
        # Match price like 98.500 or 9.150 or 7,600
        import re
        return re.findall(r"\d{1,3}(?:[.,]\d{3})", s)

    def _get_coffee_prices_rt(self):
        # Use tag page on Baoquocte to get latest article that contains domestic coffee prices
        try:
            list_url = "https://baoquocte.vn/tag/gia-ca-phe-hom-nay-185757.tag"
            r = requests.get(list_url, headers=self.headers, timeout=6)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                # Find first article link on the list
                a_tags = soup.select("a[href]")
                article_url = None
                for a in a_tags:
                    href = a.get("href", "")
                    if "gia-nong-san-hom-nay" in href or "gia-ca-phe-hom-nay" in href:
                        article_url = href
                        break
                if article_url and not article_url.startswith("http"):
                    article_url = "https://baoquocte.vn" + article_url
                if article_url:
                    ar = requests.get(article_url, headers=self.headers, timeout=6)
                    if ar.status_code == 200:
                        text = self._clean_text(ar.text)
                        provinces = ["Đắk Lắk", "Đắk Nông", "Gia Lai", "Lâm Đồng", "Kon Tum"]
                        items = []
                        for prov in provinces:
                            # find segment around province name
                            idx = text.find(prov)
                            if idx != -1:
                                seg = text[max(0, idx-80): idx+120]
                                nums = self._find_numbers(seg)
                                if nums:
                                    # Use first number as indicative price
                                    price = nums[0].replace(",", ".")
                                    items.append({"loc": prov, "price": f"{price}0", "change": "-"})
                        if items:
                            return items, f"Nguồn: Baoquocte.vn (Realtime)"
        except Exception as e:
            print(f"Coffee realtime error: {e}")
        # Fallback to previous mock if realtime fails
        return self._get_coffee_prices_mock()

    def _get_rice_prices_rt(self):
        # Pull latest article from Vietnambiz rice category, parse key varieties and ranges
        try:
            cat_url = "https://vietnambiz.vn/gia-gao.html"
            r = requests.get(cat_url, headers=self.headers, timeout=6)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                # Find first article link
                a_tags = soup.select("a[href]")
                article_url = None
                for a in a_tags:
                    href = a.get("href", "")
                    if "gia-lua-gao-hom-nay" in href or "gia-lua-gao" in href or "gia-gao-hom-nay" in href:
                        article_url = href
                        break
                if article_url and not article_url.startswith("http"):
                    article_url = "https://vietnambiz.vn" + article_url
                if article_url:
                    ar = requests.get(article_url, headers=self.headers, timeout=6)
                    if ar.status_code == 200:
                        text = self._clean_text(ar.text)
                        varieties = ["IR 504", "Đài Thơm 8", "OM 5451", "OM 18", "OM 380", "tấm thơm", "cám"]
                        items = []
                        for v in varieties:
                            idx = text.lower().find(v.lower())
                            if idx != -1:
                                seg = text[max(0, idx-80): idx+120]
                                nums = self._find_numbers(seg)
                                if nums:
                                    # Build range if two numbers found
                                    if len(nums) >= 2:
                                        price = f"{nums[0]} – {nums[1]}"
                                    else:
                                        price = nums[0]
                                    items.append({"loc": v, "price": price.replace(",", "."), "change": "-"})
                        if items:
                            return items, f"Nguồn: Vietnambiz.vn (Realtime)"
        except Exception as e:
            print(f"Rice realtime error: {e}")
        return self._get_rice_prices_mock()

market_price_service = MarketPriceService()
