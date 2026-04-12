from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os, shutil, uuid
from database import get_db, init_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

CATEGORIES = ["realestate","transport","services","clothes","kids","home","furniture","household","repair","jobs","animals","hobby","sport","electronics","food","business","money","alcohol"]
CITIES = ["sharm","hurghada","cairo","alexandria","giza","luxor"]

@app.on_event("startup")
def startup(): init_db()

@app.get("/")
def index(): return FileResponse("static/index.html")

@app.post("/api/users")
def upsert_user(telegram_id: int = Form(...), username: str = Form(None), first_name: str = Form(None)):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO users (telegram_id,username,first_name) VALUES (?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name",(telegram_id,username,first_name))
    conn.commit(); conn.close(); return {"ok":True}

@app.get("/api/listings")
def get_listings(category: str=None, city: str=None, search: str=None):
    conn = get_db(); c = conn.cursor()
    q = "SELECT * FROM listings WHERE is_active=1"; params=[]
    if category and category in CATEGORIES: q+=" AND category=?"; params.append(category)
    if city and city in CITIES: q+=" AND city=?"; params.append(city)
    if search: q+=" AND (title LIKE ? OR description LIKE ?)"; params+=[f"%{search}%",f"%{search}%"]
    q += " ORDER BY is_promoted DESC, created_at DESC"
    rows = c.execute(q,params).fetchall(); conn.close()
    return [dict(r) for r in rows]

@app.get("/api/listings/{listing_id}")
def get_listing(listing_id: int):
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT * FROM listings WHERE id=?",(listing_id,)).fetchone()
    conn.close()
    if not row: raise HTTPException(404)
    return dict(row)

def save_photo(photo):
    if not photo: return None
    ext = os.path.splitext(photo.filename)[1] or ".jpg"
    fname = f"{uuid.uuid4()}{ext}"
    with open(os.path.join(UPLOAD_DIR,fname),"wb") as f: shutil.copyfileobj(photo.file,f)
    return f"/uploads/{fname}"

@app.post("/api/listings")
async def create_listing(
    user_id: int=Form(...), title: str=Form(...), description: str=Form(None),
    price: float=Form(None), currency: str=Form("USD"),
    category: str=Form(...), city: str=Form(...),
    is_promoted: int=Form(0),
    seller_username: str=Form(None),
    photo: UploadFile=File(None),
    photo_2: UploadFile=File(None),
    photo_3: UploadFile=File(None),
    photo_4: UploadFile=File(None),
):
    if category not in CATEGORIES: raise HTTPException(400,"Invalid category")
    if city not in CITIES: raise HTTPException(400,"Invalid city")
    p1=save_photo(photo); p2=save_photo(photo_2); p3=save_photo(photo_3); p4=save_photo(photo_4)
    conn=get_db(); c=conn.cursor()
    c.execute("INSERT INTO listings (user_id,title,description,price,currency,category,city,photo_path,photo_path2,photo_path3,photo_path4,is_promoted,seller_username) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (user_id,title,description,price,currency,category,city,p1,p2,p3,p4,is_promoted,seller_username))
    conn.commit(); lid=c.lastrowid; conn.close()
    return {"ok":True,"id":lid}

@app.delete("/api/listings/{listing_id}")
def delete_listing(listing_id: int, user_id: int):
    conn=get_db(); c=conn.cursor()
    row=c.execute("SELECT user_id FROM listings WHERE id=?",(listing_id,)).fetchone()
    if not row: raise HTTPException(404)
    if row["user_id"]!=user_id: raise HTTPException(403)
    c.execute("UPDATE listings SET is_active=0 WHERE id=?",(listing_id,))
    conn.commit(); conn.close(); return {"ok":True}

if __name__=="__main__":
    import uvicorn
    uvicorn.run("api:app",host="0.0.0.0",port=8002,reload=True)
