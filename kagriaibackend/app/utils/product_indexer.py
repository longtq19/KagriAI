import os
import json
import re
from app.core.config import settings

DOCS_PRODUCTS_PATH = os.path.join(settings.DOCS_PATH, "products")

def index_products():
    products = []
    
    if not os.path.exists(DOCS_PRODUCTS_PATH):
        print(f"Products docs path not found: {DOCS_PRODUCTS_PATH}")
        return []

    for filename in os.listdir(DOCS_PRODUCTS_PATH):
        if filename.endswith(".txt"):
            file_path = os.path.join(DOCS_PRODUCTS_PATH, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if len(lines) < 3:
                        continue
                    
                    # Line 1: Source: URL
                    source_line = lines[0].strip()
                    if "Source: " in source_line:
                        url = source_line.replace("Source: ", "").strip()
                    else:
                        continue

                    # Try to parse "Tên sản phẩm / Mã sản phẩm: CODE -- NAME"
                    name = ""
                    code = ""
                    for line in lines[1:10]:  # search early lines
                        m = re.match(r"^Tên sản phẩm\s*/\s*Mã sản phẩm:\s*(.+?)\s*--\s*(.+)$", line.strip(), flags=re.IGNORECASE)
                        if m:
                            code = m.group(1).strip()
                            name = m.group(2).strip()
                            break
                    if not name:
                        # Fallback to filename as name
                        name = os.path.splitext(filename)[0].replace("-", " ").strip()
                    if not code:
                        # Fallback to code from filename
                        code = os.path.splitext(filename)[0].strip().upper()

                    products.append({
                        "code": code,
                        "name": name,
                        "url": url
                    })
            except Exception as e:
                print(f"Error reading {filename}: {e}")

    return products

if __name__ == "__main__":
    prods = index_products()
    print(f"Found {len(prods)} products.")
    for p in prods:
        print(f"- {p['code']} -- {p['name']}: {p['url']}")
