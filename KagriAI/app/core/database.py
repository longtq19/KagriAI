import sqlite3
import os
from typing import List

# Define DB path
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "db")
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DB_PATH = os.path.join(DB_DIR, "kagri.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Company Info Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS company_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        hotline TEXT,
        address TEXT,
        email TEXT,
        website TEXT,
        introduction TEXT,
        vision TEXT,
        mission TEXT,
        core_values TEXT
    )
    ''')
    
    # Create Products Table (minimal fields)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        name TEXT,
        url TEXT,
        ingredients TEXT,
        usage TEXT,
        category TEXT
    )
    ''')
    
    # Create Experts Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS experts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        title TEXT,
        degree TEXT,
        bio TEXT,
        profile_url TEXT
    )
    ''')
    
    # Ensure columns exist (for upgrades)
    def ensure_columns(table: str, columns: List[str]):
        existing = [row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
        for col in columns:
            if col not in existing:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
                except Exception as e:
                    print(f"Skip adding column {table}.{col}: {e}")
    
    ensure_columns("company_info", ["vision", "mission", "core_values", "slogan", "factories", "license_tax"])
    ensure_columns("experts", ["degree"])

    # Remove expert_team column from company_info if it exists
    existing_company_cols = [row[1] for row in cursor.execute("PRAGMA table_info(company_info)").fetchall()]
    if "expert_team" in existing_company_cols:
        print("Removing expert_team column from company_info...")
        # Get all columns except expert_team
        new_columns = [col for col in existing_company_cols if col != "expert_team"]
        new_columns_str = ", ".join(new_columns)
        
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS company_info_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                hotline TEXT,
                address TEXT,
                email TEXT,
                website TEXT,
                introduction TEXT,
                vision TEXT,
                mission TEXT,
                core_values TEXT,
                slogan TEXT,
                factories TEXT,
                license_tax TEXT
            )
        ''')
        try:
            # We need to explicitly list columns for INSERT INTO ... SELECT ...
            # But wait, company_info structure might vary with ensure_columns.
            # Safer way: Create new table with desired schema, copy matching columns.
            
            # Since we just created company_info_new with a fixed schema, let's select matching columns from old table.
            # company_info_new columns: id, name, hotline, address, email, website, introduction, vision, mission, core_values, slogan, factories, license_tax
            
            # Check which of these exist in the old table
            target_cols = ["id", "name", "hotline", "address", "email", "website", "introduction", "vision", "mission", "core_values", "slogan", "factories", "license_tax"]
            
            # Intersect with existing columns
            common_cols = [col for col in target_cols if col in existing_company_cols]
            common_cols_str = ", ".join(common_cols)
            
            cursor.execute(f'''
                INSERT INTO company_info_new ({common_cols_str})
                SELECT {common_cols_str} FROM company_info
            ''')
            
            cursor.execute('DROP TABLE company_info')
            cursor.execute('ALTER TABLE company_info_new RENAME TO company_info')
            print("Removed expert_team column successfully.")
        except Exception as e:
             print(f"Failed to remove expert_team column: {e}")

    # Normalize products table: drop unused columns if present
    existing_cols = [row[1] for row in cursor.execute("PRAGMA table_info(products)").fetchall()]
    to_remove = {"description", "benefits", "storage", "caution"}
    if any(col in existing_cols for col in to_remove):
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS products_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT,
            url TEXT,
            ingredients TEXT,
            usage TEXT,
            category TEXT
        )
        ''')
        try:
            cursor.execute('''
                INSERT INTO products_new (id, code, name, url, ingredients, usage, category)
                SELECT id, code, name, url, ingredients, usage, category FROM products
            ''')
            cursor.execute('DROP TABLE products')
            cursor.execute('ALTER TABLE products_new RENAME TO products')
            print("Products table normalized: removed description/benefits/storage/caution")
        except Exception as e:
            print(f"Failed to normalize products table: {e}")

    # Normalize experts table: drop email and phone
    existing_expert_cols = [row[1] for row in cursor.execute("PRAGMA table_info(experts)").fetchall()]
    expert_to_remove = {"email", "phone"}
    if any(col in existing_expert_cols for col in expert_to_remove):
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS experts_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            title TEXT,
            degree TEXT,
            bio TEXT,
            profile_url TEXT
        )
        ''')
        try:
            cursor.execute('''
                INSERT INTO experts_new (id, name, title, degree, bio, profile_url)
                SELECT id, name, title, degree, bio, profile_url FROM experts
            ''')
            cursor.execute('DROP TABLE experts')
            cursor.execute('ALTER TABLE experts_new RENAME TO experts')
            print("Experts table normalized: removed email/phone")
        except Exception as e:
            print(f"Failed to normalize experts table: {e}")
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_db()
