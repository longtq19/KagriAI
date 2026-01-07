import os
import sys
import re

# Ensure KagriAI root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.database import get_db_connection, init_db
from app.core.config import settings

def parse_product_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    data = {}
    
    # Parse line by line or regex
    # Format: Key: Value
    
    lines = content.splitlines()
    current_key = None
    buffer = []
    
    parsed = {}
    
    for line in lines:
        if ":" in line:
            parts = line.split(":", 1)
            # Check if the part before colon is a known key
            key_candidate = parts[0].strip()
            # Known keys map
            key_map = {
                "Tên sản phẩm / Mã sản phẩm": "name_code",
                "URL sản phẩm": "url",
                "Loại sản phẩm": "category",
                "Thành phần": "ingredients",
                "Hướng dẫn sử dụng": "usage"
            }
            
            # Simple heuristic: if key matches exactly or starts with
            found_key = None
            for k, v in key_map.items():
                if key_candidate == k:
                    found_key = v
                    break
            
            if found_key:
                # Save previous buffer
                if current_key:
                    parsed[current_key] = "\n".join(buffer).strip()
                
                current_key = found_key
                buffer = [parts[1].strip()]
                continue
        
        # Append to buffer
        if current_key:
            buffer.append(line.strip())
            
    # Save last
    if current_key:
        parsed[current_key] = "\n".join(buffer).strip()
        
    return parsed

def import_data():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Import Company Info
    print("Importing Company Info...")
    cursor.execute("DELETE FROM company_info") # Reset
    cursor.execute('''
        INSERT INTO company_info (name, hotline, address, email)
        VALUES (?, ?, ?, ?)
    ''', (
        "Công ty cổ phần Tập đoàn nông nghiệp KAGRI",
        "0985 562 582",
        "Thửa đất số T210, Khu TĐC dự án đường Dốc Hội -- ĐHNN1, Thị trấn Trâu Quỳ, Huyện Gia Lâm, Thành phố Hà Nội, Việt Nam",
        "contact@kagri.vn"
    ))
    
    # 2. Import Products
    print("Importing Products...")
    products_dir = os.path.join(settings.DOCS_PATH, "products")
    if not os.path.exists(products_dir):
        print(f"Directory not found: {products_dir}")
        return

    cursor.execute("DELETE FROM products") # Reset
    
    count = 0
    for filename in os.listdir(products_dir):
        if not filename.endswith(".txt"):
            continue
            
        filepath = os.path.join(products_dir, filename)
        data = parse_product_file(filepath)
        
        # Extract Name and Code
        name_code = data.get("name_code", "")
        if " / " in name_code:
            name, code = name_code.rsplit(" / ", 1)
        else:
            name = name_code
            code = filename.replace(".txt", "") # Fallback
            
        url = data.get("url", "")
        category = data.get("category", "")
        ingredients = data.get("ingredients", "")
        usage = data.get("usage", "")
        
        try:
            cursor.execute('''
                INSERT INTO products (code, name, url, category, ingredients, usage)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (code.strip(), name.strip(), url.strip(), category.strip(), ingredients.strip(), usage.strip()))
            count += 1
        except Exception as e:
            print(f"Error inserting {filename}: {e}")
            
    conn.commit()
    conn.close()
    print(f"Imported {count} products successfully.")

if __name__ == "__main__":
    import_data()
