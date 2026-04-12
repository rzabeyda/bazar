from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import shutil
import uuid
from database import get_db, init_db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

CATEGORIES = [
    "clothes",
    "food",
    "electronics",
    "furniture",
    "services",
    "alcohol",
    "housing",
]

CITIES = ["sharm", "hurghada"]


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def index():
    return FileResponse("static/index.html")


# --- Users ---

@app.post("/api/users")
def upsert_user(telegram_id: int = Form(...), username: str = Form(None), first_name: str = Form(None)):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (telegram_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name
    """, (telegram_id, username, first_name))
    conn.commit()
    conn.close()
    return {"ok": True}


# --- Listings ---

@app.get("/api/listings")
def get_listings(category: str = None, city: str = None, search: str = None):
    conn = get_db()
    c = conn.cursor()

    query = "SELECT * FROM listings WHERE is_active = 1"
    params = []

    if category and category in CATEGORIES:
        query += " AND category = ?"
        params.append(category)

    if city and city in CITIES:
        query += " AND city = ?"
        params.append(city)

    if search:
        query += " AND (title LIKE ? OR description LIKE ?)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")

    query += " ORDER BY created_at DESC"

    rows = c.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/listings/{listing_id}")
def get_listing(listing_id: int):
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return dict(row)


@app.post("/api/listings")
async def create_listing(
    user_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    price: float = Form(None),
    currency: str = Form("USD"),
    category: str = Form(...),
    city: str = Form(...),
    photo: UploadFile = File(None),
):
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    if city not in CITIES:
        raise HTTPException(status_code=400, detail="Invalid city")

    photo_path = None
    if photo:
        ext = os.path.splitext(photo.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        with open(save_path, "wb") as f:
            shutil.copyfileobj(photo.file, f)
        photo_path = f"/uploads/{filename}"

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO listings (user_id, title, description, price, currency, category, city, photo_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, title, description, price, currency, category, city, photo_path))
    conn.commit()
    listing_id = c.lastrowid
    conn.close()
    return {"ok": True, "id": listing_id}


@app.delete("/api/listings/{listing_id}")
def delete_listing(listing_id: int, user_id: int):
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT user_id FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    if row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    c.execute("UPDATE listings SET is_active = 0 WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/categories")
def get_categories():
    return CATEGORIES


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)
