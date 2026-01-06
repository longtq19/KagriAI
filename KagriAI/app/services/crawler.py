import requests
from bs4 import BeautifulSoup
import os
import hashlib
from app.core.config import settings
from urllib.parse import urljoin, urlparse
from app.core.database import get_db_connection, init_db
import time
import re

class KagriCrawler:
    def __init__(self, base_url="https://kagri.vn/"):
        self.base_url = base_url
        self.visited = set()
        self.docs_path = settings.DOCS_PATH
        init_db()
        self.headers = {"User-Agent": "KagriCrawler/1.0"}
        self.product_urls = set()

    def clean_text(self, text):
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return '\n'.join(chunk for chunk in chunks if chunk)

    def save_content(self, url, content):
        if not content:
            return
        
        # Create a filename from URL
        filename = hashlib.md5(url.encode()).hexdigest() + ".txt"
        filepath = os.path.join(self.docs_path, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Source: {url}\n\n")
            f.write(content)
    
    def select_main(self, soup: BeautifulSoup):
        for sel in ["#main", ".site-content", ".entry-content", "main"]:
            node = soup.select_one(sel)
            if node:
                return node
        return soup
    
    def is_product_page(self, soup: BeautifulSoup, url: str) -> bool:
        if "/san-pham/" in url:
            return True
        text = self.select_main(soup).get_text(" ").lower()
        signals = ["thành phần", "hướng dẫn sử dụng", "liều lượng", "bảo quản", "lưu ý", "mã sản phẩm", "sku"]
        return any(sig in text for sig in signals)
    
    def get_section(self, root: BeautifulSoup, keywords):
        txt = ""
        # Kagri specific IDs
        id_map = {
            "mô tả": ["MoTaSanPham"],
            "công dụng": ["CongDungSanPham"],
            "thành phần": ["ThanhPhan"],
            "hướng dẫn sử dụng": ["HuongDanSuDung"],
            "liều lượng": ["HuongDanSuDung"],
            "hướng dẫn bảo quản": ["HuongDanBaoQuan"],
            "bảo quản": ["HuongDanBaoQuan"],
            "lưu ý": ["LuuY", "LuuYKhiSuDung"],
        }
        try_ids = []
        for kw in keywords:
            try_ids.extend(id_map.get(kw, []))
        for sec_id in try_ids:
            node = root.find(id=sec_id)
            if node:
                content = node.get_text(" ").strip()
                if content:
                    txt = content
                    break
        for accordion in root.find_all(["div", "section"], id=lambda x: x and x.startswith("accordion-item-")):
            header = accordion.find(["h2", "h3", "button"])
            if header:
                t = header.get_text(" ").strip().lower()
                if any(kw in t for kw in keywords):
                    content = accordion.find(["div", "p", "section"], class_=lambda c: c and ("content" in c.lower() or "accordion" in c.lower()))
                    txt = (content.get_text(" ").strip() if content else accordion.get_text(" ").strip())
                    if txt:
                        break
        if not txt:
            for tag in root.find_all(["h2", "h3", "h4", "strong", "b"]):
                t = tag.get_text(" ").strip().lower()
                if any(kw in t for kw in keywords):
                    parts = []
                    for sib in tag.next_siblings:
                        if getattr(sib, "name", None) in ["h2", "h3", "h4", "strong", "b"]:
                            break
                        parts.append(getattr(sib, "get_text", lambda *a, **k: str(sib))(" ").strip())
                    txt = "\n".join([p for p in parts if p]).strip()
                    if txt:
                        break
        if not txt:
            text = root.get_text("\n")
            lower = text.lower()
            # Define stop keywords (boundaries)
            stops = [
                "thành phần", "hướng dẫn sử dụng", "liều lượng",
                "hướng dẫn bảo quản", "bảo quản", "lưu ý khi sử dụng", "lưu ý",
                "mô tả sản phẩm", "công dụng sản phẩm"
            ]
            for kw in keywords:
                i = lower.find(kw)
                if i != -1:
                    # find nearest next stop after i
                    j = None
                    for s in stops:
                        pos = lower.find(s, i + 1)
                        if pos != -1 and (j is None or pos < j):
                            j = pos
                    seg = text[i:j] if j else text[i:]
                    txt = seg.strip()
                    break
        return txt
    
    def get_category(self, root: BeautifulSoup):
        # Prefer breadcrumbs with product-category
        for a in root.select(".woocommerce-breadcrumb a"):
            href = a.get("href", "")
            if "/product-category/" in href:
                return a.get_text(strip=True)
        # Try any link to product-category on page
        for a in root.find_all("a", href=True):
            if "/product-category/" in a["href"]:
                return a.get_text(strip=True)
        # WooCommerce posted_in
        for sel in [".product_meta .posted_in a", ".posted_in a"]:
            node = root.select_one(sel)
            if node:
                return node.get_text(strip=True)
        # Fallback by label text
        meta = root.select_one(".product_meta") or root
        text = meta.get_text("\n")
        m = re.search(r"(Danh mục|Loại sản phẩm)\\s*:\\s*(.+)", text, flags=re.IGNORECASE)
        if m:
            return m.group(2).strip().split("\n")[0]
        # Fallback to breadcrumb last meaningful item
        crumbs = root.select(".woocommerce-breadcrumb a")
        if crumbs:
            names = [c.get_text(strip=True) for c in crumbs]
            for name in reversed(names):
                if name.lower() not in ["trang chủ", "sản phẩm"]:
                    return name
        return ""
    
    def parse_product(self, soup: BeautifulSoup, url: str):
        root = self.select_main(soup)
        name_node = root.select_one("h1") or soup.select_one("h1")
        name = name_node.get_text(strip=True) if name_node else ""
        base_url = url.split("#")[0].split("?")[0]
        sku_node = root.select_one(".sku")
        code = sku_node.get_text(strip=True) if sku_node else ""
        if not code:
            text = root.get_text(" ")
            for kw in ["mã sản phẩm", "sku", "mã số"]:
                idx = text.lower().find(kw)
                if idx != -1:
                    seg = text[idx:idx+200]
                    parts = seg.split(":")
                    if len(parts) > 1:
                        code = parts[1].strip().split("\n")[0]
                        break
        if not code:
            code = hashlib.md5(base_url.encode()).hexdigest()[:8]
        category = self.get_category(root)
        ingredients = self.get_section(root, ["thành phần"])
        usage = self.get_section(root, ["hướng dẫn sử dụng", "liều lượng"])
        description = self.get_section(root, ["mô tả sản phẩm", "mô tả"])
        benefits = self.get_section(root, ["công dụng", "tác dụng", "lợi ích"])
        storage = self.get_section(root, ["hướng dẫn bảo quản", "bảo quản"])
        caution = self.get_section(root, ["lưu ý khi sử dụng", "lưu ý"])
        return {
            "code": code,
            "name": name,
            "url": base_url,
            "category": category,
            "ingredients": ingredients,
            "usage": usage,
            "description": description,
            "benefits": benefits,
            "storage": storage,
            "caution": caution
        }
    
    def upsert_product(self, data: dict):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO products (code, name, url, category, ingredients, usage, description, benefits, storage, caution)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name=excluded.name,
                    url=excluded.url,
                    category=excluded.category,
                    ingredients=excluded.ingredients,
                    usage=excluded.usage,
                    description=excluded.description,
                    benefits=excluded.benefits,
                    storage=excluded.storage,
                    caution=excluded.caution
            ''', (
                data["code"], data["name"], data["url"], data["category"], data["ingredients"], data["usage"],
                data["description"], data["benefits"], data["storage"], data["caution"]
            ))
            conn.commit()
        except Exception as e:
            print(f"DB error inserting product {data.get('code')}: {e}")
        finally:
            conn.close()
    
    def extract_company_info(self, soup: BeautifulSoup, url: str):
        root = self.select_main(soup)
        text = self.clean_text(root.get_text())
        def find_value(keys):
            for k in keys:
                val = self.get_section(root, [k])
                if val:
                    return val.strip()
            return ""
        name = find_value(["tên đầy đủ của công ty", "tên công ty"]) or "Công ty cổ phần Tập đoàn nông nghiệp KAGRI"
        hotline = find_value(["hotline", "số điện thoại"])
        email = find_value(["email"])
        address = find_value(["địa chỉ"])
        introduction = find_value(["giới thiệu", "về chúng tôi"])
        vision = find_value(["tầm nhìn"])
        mission = find_value(["sứ mệnh"])
        core_values = find_value(["giá trị cốt lõi"])
        expert_team = find_value(["đội ngũ chuyên gia"])
        return {
            "name": name, "hotline": hotline, "email": email, "address": address,
            "website": "https://kagri.vn/", "introduction": introduction,
            "vision": vision, "mission": mission, "core_values": core_values, "expert_team": expert_team
        }
    
    def upsert_company_info(self, info: dict):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM company_info")
            cur.execute('''
                INSERT INTO company_info (name, hotline, address, email, website, introduction, vision, mission, core_values, expert_team)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                info["name"], info["hotline"], info["address"], info["email"], info["website"], info["introduction"],
                info["vision"], info["mission"], info["core_values"], info["expert_team"]
            ))
            conn.commit()
        except Exception as e:
            print(f"DB error inserting company info: {e}")
        finally:
            conn.close()
    
    def parse_experts(self, soup: BeautifulSoup, url: str):
        experts = []
        for card in soup.find_all(["section", "div"], string=lambda s: s and ("chuyên gia" in s.lower())):
            name = card.get_text(strip=True)
            experts.append({"name": name, "title": "", "bio": "", "email": "", "phone": "", "profile_url": url})
            if len(experts) >= 2:
                break
        return experts
    
    def upsert_experts(self, experts):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM experts")
            for e in experts[:2]:
                cur.execute('''
                    INSERT INTO experts (name, title, bio, email, phone, profile_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (e["name"], e["title"], e["bio"], e["email"], e["phone"], e["profile_url"]))
            conn.commit()
        except Exception as e:
            print(f"DB error inserting experts: {e}")
        finally:
            conn.close()

    def crawl(self, max_pages=20):
        queue = [self.base_url]
        count = 0
        
        if not os.path.exists(self.docs_path):
            os.makedirs(self.docs_path)

        while queue and count < max_pages:
            url = queue.pop(0)
            if url in self.visited:
                continue
            
            print(f"Crawling: {url}")
            try:
                response = requests.get(url, timeout=10, headers=self.headers)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove scripts and styles
                for script in soup(["script", "style"]):
                    script.extract()
                    
                # Company info extraction heuristic
                if any(k in url for k in ["gioi-thieu", "ve-chung-toi", "about", "company", "chung-toi"]):
                    info = self.extract_company_info(soup, url)
                    self.upsert_company_info(info)
                
                # Experts page extraction
                if any(k in url for k in ["chuyen-gia", "experts", "doi-ngu-chuyen-gia"]):
                    experts = self.parse_experts(soup, url)
                    if experts:
                        self.upsert_experts(experts)
                
                # Product page detection and parsing
                if self.is_product_page(soup, url):
                    product = self.parse_product(soup, url)
                    self.upsert_product(product)
                    base_url = url.split("#")[0].split("?")[0]
                    self.product_urls.add(base_url)
                else:
                    # Save raw content for future RAG build if needed
                    text = soup.get_text()
                    cleaned_text = self.clean_text(text)
                    self.save_content(url, cleaned_text)
                
                self.visited.add(url)
                count += 1
                
                # Find links
                for link in soup.find_all('a', href=True):
                    full_url = urljoin(url, link['href'])
                    if "#" in full_url:
                        full_url = full_url.split("#")[0]
                    if "wp-content/uploads" in full_url:
                        continue
                    parsed = urlparse(full_url)
                    # Only internal links
                    if parsed.netloc == urlparse(self.base_url).netloc:
                        base = full_url.split("?")[0].rstrip("/")
                        if base and base not in self.visited:
                            queue.append(base)
                time.sleep(0.2)
                             
            except Exception as e:
                print(f"Error crawling {url}: {e}")
        
        # After crawl, prune DB to match current website products
        try:
            self.prune_products()
        except Exception as e:
            print(f"Prune error: {e}")
    
    def prune_products(self):
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            rows = cur.execute("SELECT id, url FROM products").fetchall()
            def norm(u):
                if not u:
                    return ""
                try:
                    p = urlparse(u)
                    host = p.netloc.lower()
                    if host.startswith("www."):
                        host = host[4:]
                    path = p.path.rstrip("/")
                    return f"{host}{path}"
                except Exception:
                    return (u or "").split("#")[0].split("?")[0].rstrip("/").lower().replace("http://", "").replace("https://", "").lstrip("www.")
            urls_in_db = {norm(row["url"]) for row in rows if row["url"]}
            archive = self.get_archive_product_links()
            discovered = set(self.product_urls)
            keep_raw = archive if archive else discovered
            keep = {norm(u) for u in keep_raw}
            to_delete = [row["id"] for row in rows if norm(row["url"]) not in keep]
            for pid in to_delete:
                cur.execute("DELETE FROM products WHERE id = ?", (pid,))
            conn.commit()
            print(f"Pruned {len(to_delete)} products not present on website. Kept {len(keep)}.")
            # Deduplicate by normalized URL, keeping lowest id
            rows2 = cur.execute("SELECT id, url, description, benefits, usage, ingredients FROM products ORDER BY id ASC").fetchall()
            by_url = {}
            for r in rows2:
                u = norm(r["url"])
                score = sum(len(r[k] or "") for k in ["description", "benefits", "usage", "ingredients"])
                if not u:
                    # Remove rows with empty URL
                    by_url.setdefault("", []).append((score, r["id"]))
                    continue
                by_url.setdefault(u, []).append((score, r["id"]))
            dup_ids = []
            for u, items in by_url.items():
                if len(items) <= 1:
                    # Keep the only item
                    continue
                # Keep the one with highest score; if tie, keep lowest id
                keep_id = sorted(items, key=lambda x: (-x[0], x[1]))[0][1]
                for score, rid in items:
                    if rid != keep_id:
                        dup_ids.append(rid)
            for did in dup_ids:
                cur.execute("DELETE FROM products WHERE id = ?", (did,))
            conn.commit()
            if dup_ids:
                print(f"Removed {len(dup_ids)} duplicate/empty URL product rows.")
        finally:
            conn.close()
    
    def sync_missing_products(self):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            def norm(u):
                if not u:
                    return ""
                try:
                    p = urlparse(u)
                    host = p.netloc.lower()
                    if host.startswith("www."):
                        host = host[4:]
                    path = p.path.rstrip("/")
                    return f"{host}{path}"
                except Exception:
                    return (u or "").split("#")[0].split("?")[0].rstrip("/").lower().replace("http://", "").replace("https://", "").lstrip("www.")
            rows = cur.execute("SELECT url FROM products").fetchall()
            present = {norm(row["url"]) for row in rows if row["url"]}
            keep_urls = self.get_archive_product_links()
            targets = [u for u in keep_urls if norm(u) not in present]
            print(f"Syncing {len(targets)} missing products...")
            for u in targets:
                try:
                    r = requests.get(u, timeout=10, headers=self.headers)
                    if r.status_code != 200:
                        continue
                    soup = BeautifulSoup(r.text, "html.parser")
                    for script in soup(["script", "style"]):
                        script.extract()
                    data = self.parse_product(soup, u)
                    self.upsert_product(data)
                    time.sleep(0.1)
                except Exception as e:
                    print(f"Sync error for {u}: {e}")
            conn.close()
        except Exception as e:
            print(f"Sync missing products error: {e}")
    
    def get_archive_product_links(self):
        urls = set()
        try:
            # Collect from /san-pham/ archive pages
            page = 1
            while True:
                path = f"{self.base_url.rstrip('/')}/san-pham/"
                if page > 1:
                    path = f"{path}page/{page}/"
                r = requests.get(path, timeout=10, headers=self.headers)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "/san-pham/" in href:
                        base = href.split("#")[0].split("?")[0]
                        if "/san-pham/page/" in base or base.rstrip("/").endswith("/san-pham"):
                            continue
                        urls.add(base.rstrip("/"))
                # detect next page
                next_link = soup.select_one("a.next, a.page-numbers.next")
                if next_link and next_link.get("href"):
                    page += 1
                    continue
                break
            # Collect from XML sitemaps if available
            try:
                candidates = [
                    f"{self.base_url.rstrip('/')}/product-sitemap.xml",
                    f"{self.base_url.rstrip('/')}/sitemap.xml",
                    f"{self.base_url.rstrip('/')}/sitemap_index.xml",
                ]
                for sm in candidates:
                    rs = requests.get(sm, timeout=8, headers=self.headers)
                    if rs.status_code != 200 or ("<html" in rs.text.lower()):
                        continue
                    ssoup = BeautifulSoup(rs.text, "xml")
                    for loc in ssoup.find_all("loc"):
                        loc_url = loc.get_text().strip()
                        if "/san-pham/" in loc_url:
                            base = loc_url.split("#")[0].split("?")[0].rstrip("/")
                            urls.add(base)
                        # Follow product sitemap parts
                        if "-product-" in loc_url or "product-sitemap" in loc_url:
                            try:
                                r2 = requests.get(loc_url, timeout=8, headers=self.headers)
                                if r2.status_code == 200:
                                    s2 = BeautifulSoup(r2.text, "xml")
                                    for loc2 in s2.find_all("loc"):
                                        u2 = loc2.get_text().strip()
                                        if "/san-pham/" in u2:
                                            urls.add(u2.split("#")[0].split("?")[0].rstrip("/"))
                            except Exception:
                                pass
            except Exception:
                pass
            # Collect from /shop/ pages
            try:
                p = 1
                while True:
                    shop_path = f"{self.base_url.rstrip('/')}/shop/"
                    if p > 1:
                        shop_path = f"{shop_path}page/{p}/"
                    rs = requests.get(shop_path, timeout=10, headers=self.headers)
                    if rs.status_code != 200:
                        break
                    ssoup = BeautifulSoup(rs.text, "html.parser")
                    for a in ssoup.find_all("a", href=True):
                        href = a["href"]
                        if "/san-pham/" in href:
                            base = href.split("#")[0].split("?")[0].rstrip("/")
                            if "/san-pham/page/" in base or base.rstrip("/").endswith("/san-pham"):
                                continue
                            urls.add(base)
                    next_link = ssoup.select_one("a.next, a.page-numbers.next, a.page-numbers[rel='next']")
                    if next_link and next_link.get("href"):
                        p += 1
                        continue
                    break
            except Exception as e:
                pass
            # Collect from product-category pages discovered on homepage
            try:
                r = requests.get(self.base_url, timeout=10, headers=self.headers)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    cat_links = set()
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if "/product-category/" in href:
                            cat_links.add(href.split("#")[0].split("?")[0].rstrip("/"))
                    for cat in list(cat_links)[:20]:
                        p = 1
                        while True:
                            cat_path = cat
                            if p > 1:
                                cat_path = f"{cat}/page/{p}/"
                            rc = requests.get(cat_path, timeout=10, headers=self.headers)
                            if rc.status_code != 200:
                                break
                            csoup = BeautifulSoup(rc.text, "html.parser")
                            for a in csoup.find_all("a", href=True):
                                href = a["href"]
                                if "/san-pham/" in href:
                                    base = href.split("#")[0].split("?")[0].rstrip("/")
                                    urls.add(base)
                            next_link = csoup.select_one("a.next, a.page-numbers.next, a.page-numbers[rel='next']")
                            if next_link and next_link.get("href"):
                                p += 1
                                continue
                            break
            except Exception as e:
                pass
            return urls
        except Exception as e:
            print(f"Archive parse error: {e}")
            return set()
    
    def validate_and_update_product(self, url: str):
        try:
            r = requests.get(url, timeout=10, headers=self.headers)
            if r.status_code != 200:
                print(f"Validate: cannot fetch {url}, status={r.status_code}")
                return None
            soup = BeautifulSoup(r.text, "html.parser")
            for script in soup(["script", "style"]):
                script.extract()
            data = self.parse_product(soup, url)
            self.upsert_product(data)
            conn = get_db_connection()
            row = conn.execute("SELECT * FROM products WHERE url = ?", (url,)).fetchone()
            conn.close()
            print(f"Validated and updated product: {url}")
            return row
        except Exception as e:
            print(f"Validate error for {url}: {e}")
            return None

crawler = KagriCrawler()
