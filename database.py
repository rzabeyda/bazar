import sqlite3, os
DB_PATH = os.path.join(os.path.dirname(__file__), "bazar.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, telegram_id INTEGER UNIQUE NOT NULL,
        username TEXT, first_name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT,
        price REAL, currency TEXT DEFAULT 'USD', category TEXT NOT NULL,
        city TEXT NOT NULL,
        photo_path TEXT, photo_path2 TEXT, photo_path3 TEXT, photo_path4 TEXT,
        is_promoted INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
        seller_username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP DEFAULT (datetime('now','+30 days')),
        notified_expiry INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(telegram_id))""")
    # migrations
    for col, defn in [
        ("photo_path2","TEXT"), ("photo_path3","TEXT"), ("photo_path4","TEXT"),
        ("is_promoted","INTEGER DEFAULT 0"), ("seller_username","TEXT"),
        ("expires_at","TIMESTAMP DEFAULT (datetime('now','+30 days'))"),
        ("notified_expiry","INTEGER DEFAULT 0"),
    ]:
        try: c.execute(f"ALTER TABLE listings ADD COLUMN {col} {defn}")
        except: pass
    conn.commit(); conn.close(); print("DB initialized")

if __name__=="__main__": init_db()
