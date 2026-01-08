import sqlite3
import os
from typing import List, Optional

# Define DB path
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "db")
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DB_PATH = os.path.join(DB_DIR, "kagri.db")
CHAT_DB_PATH = os.path.join(DB_DIR, "chat.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_chat_db_connection():
    conn = sqlite3.connect(CHAT_DB_PATH)
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
    # Remove chat tables from main DB if exist
    existing_tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    for t in ["chat_sessions", "chat_turns"]:
        if t in existing_tables:
            try:
                cursor.execute(f"DROP TABLE {t}")
                print(f"Dropped legacy {t} from main DB")
            except Exception as e:
                print(f"Failed to drop {t}: {e}")

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
    
def save_chat_session(session_id: str, turns: list, last_product_code: Optional[str]):
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_sessions (session_id, last_product_code, created_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id) DO UPDATE SET
            last_product_code=excluded.last_product_code,
            updated_at=CURRENT_TIMESTAMP
    ''', (session_id, last_product_code))
    cursor.execute('DELETE FROM chat_turns WHERE session_id = ?', (session_id,))
    for idx, t in enumerate(turns):
        cursor.execute('''
            INSERT INTO chat_turns (session_id, turn_index, user, ai, user_image_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, idx, t.get("user", ""), t.get("ai", ""), t.get("user_image_path")))
    conn.commit()
    conn.close()
    
def load_chat_session(session_id: str):
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    session_row = cursor.execute('SELECT session_id, last_product_code FROM chat_sessions WHERE session_id = ?', (session_id,)).fetchone()
    if not session_row:
        conn.close()
        return None
    turn_rows = cursor.execute('SELECT user, ai FROM chat_turns WHERE session_id = ? ORDER BY turn_index ASC', (session_id,)).fetchall()
    conn.close()
    turns = [{"user": r["user"], "ai": r["ai"]} for r in turn_rows]
    return {"turns": turns, "meta": {"last_product_code": session_row["last_product_code"]}}

def append_chat_turn(session_id: str, user: str, ai: str, user_image_path: Optional[str] = None, last_product_code: Optional[str] = None):
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_sessions (session_id, last_product_code, created_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id) DO UPDATE SET
            last_product_code=COALESCE(excluded.last_product_code, chat_sessions.last_product_code),
            updated_at=CURRENT_TIMESTAMP
    ''', (session_id, last_product_code))
    next_idx_row = cursor.execute('SELECT COALESCE(MAX(turn_index), -1) + 1 AS next_idx FROM chat_turns WHERE session_id = ?', (session_id,)).fetchone()
    next_idx = next_idx_row["next_idx"] if next_idx_row else 0
    cursor.execute('''
        INSERT INTO chat_turns (session_id, turn_index, user, ai, user_image_path)
        VALUES (?, ?, ?, ?, ?)
    ''', (session_id, next_idx, user, ai, user_image_path))
    conn.commit()
    conn.close()

def append_user_turn(session_id: str, user: str, user_image_path: Optional[str] = None, last_product_code: Optional[str] = None) -> int:
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_sessions (session_id, last_product_code, created_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id) DO UPDATE SET
            last_product_code=COALESCE(excluded.last_product_code, chat_sessions.last_product_code),
            updated_at=CURRENT_TIMESTAMP
    ''', (session_id, last_product_code))
    next_idx_row = cursor.execute('SELECT COALESCE(MAX(turn_index), -1) + 1 AS next_idx FROM chat_turns WHERE session_id = ?', (session_id,)).fetchone()
    next_idx = next_idx_row["next_idx"] if next_idx_row else 0
    cursor.execute('''
        INSERT INTO chat_turns (session_id, turn_index, user, ai, user_image_path)
        VALUES (?, ?, ?, ?, ?)
    ''', (session_id, next_idx, user, "", user_image_path))
    conn.commit()
    conn.close()
    return next_idx

def update_ai_turn(session_id: str, turn_index: int, ai: str):
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE chat_turns
        SET ai = ?
        WHERE session_id = ? AND turn_index = ?
    ''', (ai, session_id, turn_index))
    conn.commit()
    conn.close()

def update_user_image_path(session_id: str, turn_index: int, user_image_path: str):
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE chat_turns
        SET user_image_path = ?
        WHERE session_id = ? AND turn_index = ?
    ''', (user_image_path, session_id, turn_index))
    conn.commit()
    conn.close()

def init_chat_db():
    conn = get_chat_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_sessions (
        session_id TEXT PRIMARY KEY,
        last_product_code TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        turn_index INTEGER,
        user TEXT,
        ai TEXT,
        user_image_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    # Ensure column exists
    existing = [row[1] for row in cursor.execute("PRAGMA table_info(chat_turns)").fetchall()]
    if "user_image_path" not in existing:
        try:
            cursor.execute("ALTER TABLE chat_turns ADD COLUMN user_image_path TEXT")
        except Exception as e:
            print(f"Skip adding column chat_turns.user_image_path: {e}")
    conn.commit()
    conn.close()
    print(f"Chat database initialized at {CHAT_DB_PATH}")
