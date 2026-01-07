import os
import re
import sys
import argparse
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

# Ensure KagriAI root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.config import settings
from app.services.rag_engine import rag_engine

def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path)

def clean_text(text: str) -> str:
    if not text:
        return ""
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return '\n'.join(chunk for chunk in chunks if chunk)

def extract_section(soup: BeautifulSoup, section_name: str) -> str:
    """
    Helper to extract content following a header/strong tag with section_name.
    """
    # Try finding strong/b/h2/h3/h4/p containing the section name
    # Then get the next siblings until the next header
    
    # Normalize section_name for regex
    pattern = re.compile(re.escape(section_name), re.IGNORECASE)
    
    # Search for element containing text
    start_elem = soup.find(text=pattern)
    if not start_elem:
        # Try finding in strong/b directly
        for tag in ['strong', 'b', 'h2', 'h3', 'h4', 'span']:
            found = soup.find(tag, string=pattern)
            if found:
                start_elem = found
                break
    
    if not start_elem:
        return ""

    # If start_elem is NavigableString, get its parent
    if hasattr(start_elem, 'parent') and start_elem.parent:
        start_node = start_elem.parent
    else:
        start_node = start_elem

    content = []
    
    # Gather siblings
    curr = start_node.next_sibling
    while curr:
        if curr.name in ['h2', 'h3', 'h4', 'strong', 'b'] and len(curr.get_text(strip=True)) > 5:
             # Stop at next header-like element (heuristic)
             # But check if it's just a small bold text or a real header
             break
        
        if curr.name:
             text = curr.get_text(separator="\n", strip=True)
             if text:
                 content.append(text)
        elif isinstance(curr, str):
             text = curr.strip()
             if text:
                 content.append(text)
        
        curr = curr.next_sibling
        
    return "\n".join(content)

def parse_product_page(url: str) -> dict:
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Title / Name
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = clean_text(h1.get_text())
        if not title and soup.title:
            title = clean_text(soup.title.string)

        # 3. Code (Mã sản phẩm)
        code = ""
        # Look for explicit "Mã sản phẩm: ..."
        # Often in .product_meta or similar
        meta_div = soup.find(class_="product_meta") or soup.find(class_="product_detail")
        if meta_div:
            meta_text = meta_div.get_text()
            m = re.search(r"(Mã sản phẩm|SKU)[:：]\s*([A-Z0-9\-_]+)", meta_text, re.IGNORECASE)
            if m:
                code = m.group(2).strip()
        
        if not code:
            # Fallback: Slug (Most reliable fallback)
            code = url.rstrip("/").split("/")[-1].upper().replace("-", "_")

        # 4. Category (Loại sản phẩm)
        category = ""
        # Often in breadcrumbs or posted_in
        posted_in = soup.find(class_="posted_in")
        if posted_in:
             category = clean_text(posted_in.get_text().replace("Danh mục:", "").replace("Category:", ""))
        
        # 5. Extract specific sections
        # We search in the main content area to avoid header/footer noise
        main_content = soup.find(class_="entry-content") or soup.find(class_="product-details") or soup.find("main") or soup

        # Helper to find text by keyword in main_content
        def find_content_by_keyword(keywords):
            for kw in keywords:
                res = extract_section(main_content, kw)
                if res: return res
            return ""

        # Map requested fields
        
        # Mô tả sản phẩm:
        # Use short description if available, otherwise try to find general text at start of main content
        desc_div = soup.find(class_="woocommerce-product-details__short-description") or soup.find(class_="short-description")
        description = clean_text(desc_div.get_text()) if desc_div else ""
        
        # If description is still empty, maybe the first few paragraphs of main_content?
        # But let's stick to strict extraction for now.
        
        # Công dụng sản phẩm:
        uses = find_content_by_keyword(["Công dụng", "Tác dụng", "Lợi ích"])
        
        # Thành phần:
        ingredients = find_content_by_keyword(["Thành phần", "Chất hữu cơ", "Hàm lượng"])
        
        # Hướng dẫn sử dụng:
        usage = find_content_by_keyword(["Hướng dẫn sử dụng", "Cách dùng", "Liều dùng", "Liều lượng"])
        
        # Hướng dẫn bảo quản:
        storage = find_content_by_keyword(["Bảo quản", "Hướng dẫn bảo quản"])
        
        # Lưu ý khi sử dụng:
        notes = find_content_by_keyword(["Lưu ý", "Chú ý", "Cảnh báo"])
        
        # Đánh giá của khách hàng:
        # Usually in reviews tab
        reviews = ""
        reviews_tab = soup.find(id="reviews") or soup.find(class_="reviews_tab")
        if reviews_tab:
            reviews = clean_text(reviews_tab.get_text())

        return {
            "title": title,
            "code": code,
            "url": url,
            "category": category,
            "description": description,
            "uses": uses,
            "ingredients": ingredients,
            "usage": usage,
            "storage": storage,
            "notes": notes,
            "reviews": reviews
        }

    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return {}

def save_product(data: dict, out_dir: str):
    code = data.get("code", "UNKNOWN").replace("/", "_").replace("\\", "_") # Sanitize filename
    filename = f"{code}.txt"
    filepath = os.path.join(out_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"Tên sản phẩm / Mã sản phẩm: {data['title']} / {data['code']}\n")
        f.write(f"URL sản phẩm: {data['url']}\n")
        f.write(f"Loại sản phẩm: {data['category']}\n")
        f.write(f"Mô tả sản phẩm: {data['description']}\n")
        f.write(f"Công dụng sản phẩm: {data['uses']}\n")
        f.write(f"Thành phần: {data['ingredients']}\n")
        f.write(f"Hướng dẫn sử dụng: {data['usage']}\n")
        f.write(f"Hướng dẫn bảo quản: {data['storage']}\n")
        f.write(f"Lưu ý khi sử dụng: {data['notes']}\n")
        f.write(f"Đánh giá của khách hàng: {data['reviews']}\n")

def get_products_from_sitemap(sitemap_url: str) -> set:
    try:
        resp = requests.get(sitemap_url, timeout=10)
        if resp.status_code != 200:
            return set()
        
        soup = BeautifulSoup(resp.content, "xml") # Use XML parser
        urls = set()
        for loc in soup.find_all("loc"):
            url = loc.get_text().strip()
            if "/san-pham/" in url:
                urls.add(url)
        return urls
    except Exception as e:
        print(f"Error parsing sitemap {sitemap_url}: {e}")
        return set()

def crawl_all_products(base_url: str):
    out_dir = os.path.join(settings.DOCS_PATH, "products")
    ensure_dir(out_dir)
    
    # 1. Try Sitemap first
    print("Checking sitemaps...")
    product_urls = set()
    
    # Try common sitemap locations
    sitemaps = [
        urljoin(base_url, "product-sitemap.xml"),
        urljoin(base_url, "sitemap.xml"),
        urljoin(base_url, "wp-sitemap.xml"),
    ]
    
    for sm in sitemaps:
        print(f"Checking {sm}...")
        found = get_products_from_sitemap(sm)
        if found:
            print(f"Found {len(found)} products in {sm}")
            product_urls.update(found)
            # If we found product-sitemap.xml, we usually have them all
            if "product-sitemap.xml" in sm:
                break
    
    # 2. If sitemap failed or empty, fallback to scanning pages
    if not product_urls:
        print("Sitemap not found or empty. Fallback to scanning pages...")
        page = 1
        while True:
            # Try common pagination patterns for WordPress/WooCommerce
            if page == 1:
                list_url = urljoin(base_url, "san-pham/") # or "cua-hang/" or "shop/"
            else:
                list_url = urljoin(base_url, f"san-pham/page/{page}/")
                
            print(f"Scanning page {page}: {list_url}")
            try:
                resp = requests.get(list_url, timeout=10)
                if resp.status_code == 404:
                    break
                
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.find_all("a", href=True)
                
                found_on_page = 0
                for a in links:
                    href = a['href']
                    # Check if it's a product URL (usually contains /san-pham/product-slug)
                    # And NOT a category or tag archive
                    if "/san-pham/" in href and href != list_url and "/page/" not in href and "/danh-muc/" not in href:
                         # Verify it's not just a link back to shop page
                         if href not in product_urls:
                             product_urls.add(href)
                             found_on_page += 1
                
                if found_on_page == 0:
                    # Might be end of pagination or different structure
                    # Let's check if there is a 'next' button
                    next_btn = soup.find("a", class_="next")
                    if not next_btn:
                        break
                
                page += 1
            except Exception as e:
                print(f"Error scanning page {page}: {e}")
                break
            
    print(f"Found total {len(product_urls)} products.")
    
    # 3. Process each product
    for i, url in enumerate(product_urls):
        print(f"[{i+1}/{len(product_urls)}] Processing: {url}")
        try:
            data = parse_product_page(url)
            if data and data.get("title"):
                save_product(data, out_dir)
        except Exception as e:
            print(f"Failed to process {url}: {e}")
            
    # 4. Rebuild Index
    print("Rebuilding RAG index...")
    rag_engine.build_index()
    print("Done.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://kagri.vn/", help="Base URL")
    args = parser.parse_args()
    
    crawl_all_products(args.url)

if __name__ == "__main__":
    main()
