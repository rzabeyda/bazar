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
    c.execute("""CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER NOT NULL,
        listing_title TEXT,
        seller_id INTEGER NOT NULL,
        buyer_id INTEGER NOT NULL,
        buyer_username TEXT,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'USD',
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (listing_id) REFERENCES listings(id))""")
    # migrations listings
    for col, defn in [
        ("photo_path2","TEXT"), ("photo_path3","TEXT"), ("photo_path4","TEXT"),
        ("photo_path5","TEXT"), ("photo_path6","TEXT"), ("photo_path7","TEXT"), ("photo_path8","TEXT"),
        ("is_promoted","INTEGER DEFAULT 0"), ("seller_username","TEXT"),
        ("expires_at","TIMESTAMP DEFAULT (datetime('now','+30 days'))"),
        ("notified_expiry","INTEGER DEFAULT 0"),
        ("phone","TEXT"),
        ("promoted_until","TIMESTAMP"),
        ("is_legendary","INTEGER DEFAULT 0"),
        ("legendary_until","TIMESTAMP"),
        ("condition","TEXT DEFAULT 'new'"),
        ("views","INTEGER DEFAULT 0"),
    ]:
        try: c.execute(f"ALTER TABLE listings ADD COLUMN {col} {defn}")
        except: pass
    # migrations users
    for col, defn in [
        ("is_verified","INTEGER DEFAULT 0"),
        ("verified_until","TIMESTAMP"),
    ]:
        try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
        except: pass
    # messages table
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        listing_id INTEGER,
        text TEXT NOT NULL,
        sender_username TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    # reports table
    c.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER NOT NULL,
        reporter_id INTEGER,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit(); conn.close(); print("DB initialized")

if __name__=="__main__": init_db()
