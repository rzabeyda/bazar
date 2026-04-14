from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os, shutil, uuid
from dotenv import load_dotenv
load_dotenv()
from database import get_db, init_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

CATEGORIES = ["realestate","rent","transport","services","beauty","clothes","kids","home","furniture","household","repair","jobs","animals","hobby","sport","electronics","food","business","money","alcohol","smoking","tours","excursions","medicine","education","other"]
CITIES = ["sharm","hurghada","cairo","alexandria","dahab","marsa","el-gouna","taba","luxor","aswan","safaga","el-quseir","nuweiba","soma-bay","other"]

def validate_city(city: str) -> bool:
    return city in CITIES or (0 < len(city) <= 60)

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
    q = """SELECT l.*, u.is_verified, u.verified_until
           FROM listings l LEFT JOIN users u ON l.user_id=u.telegram_id
           WHERE l.is_active=1"""; params=[]
    if category and category in CATEGORIES: q+=" AND l.category=?"; params.append(category)
    if city: q+=" AND l.city=?"; params.append(city)
    if search: q+=" AND (l.title LIKE ? OR l.description LIKE ?)"; params+=[f"%{search}%",f"%{search}%"]
    q += " ORDER BY l.is_legendary DESC, l.is_promoted DESC, l.created_at DESC"
    rows = c.execute(q,params).fetchall(); conn.close()
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = []
    for r in rows:
        d = dict(r)
        d["seller_verified"] = bool(r["is_verified"] and (not r["verified_until"] or r["verified_until"] > now))
        result.append(d)
    return result

# IMPORTANT: sold route must be before /{listing_id} to avoid conflict
@app.get("/api/listings/sold/{user_id}")
def get_sold(user_id: int):
    conn=get_db(); c=conn.cursor()
    rows=c.execute("SELECT * FROM listings WHERE user_id=? AND is_active=2 ORDER BY created_at DESC",(user_id,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

@app.get("/api/listings/{listing_id}")
def get_listing(listing_id: int, viewer_id: int = None):
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT * FROM listings WHERE id=?",(listing_id,)).fetchone()
    if not row: raise HTTPException(404)
    # increment views (only if not owner)
    if viewer_id and viewer_id != row["user_id"]:
        c.execute("UPDATE listings SET views=COALESCE(views,0)+1 WHERE id=?",(listing_id,))
        conn.commit()
    # get seller verification
    seller = c.execute("SELECT is_verified, verified_until FROM users WHERE telegram_id=?",(row["user_id"],)).fetchone()
    conn.close()
    d = dict(row)
    if seller:
        now = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        d["seller_verified"] = bool(seller["is_verified"] and (not seller["verified_until"] or seller["verified_until"] > now))
    else:
        d["seller_verified"] = False
    return d

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
    phone: str=Form(None),
    condition: str=Form("new"),
    photo: UploadFile=File(None),
    photo_2: UploadFile=File(None),
    photo_3: UploadFile=File(None),
    photo_4: UploadFile=File(None),
    photo_5: UploadFile=File(None),
    photo_6: UploadFile=File(None),
    photo_7: UploadFile=File(None),
    photo_8: UploadFile=File(None),
):
    if category not in CATEGORIES: raise HTTPException(400,"Invalid category")
    if not validate_city(city): raise HTTPException(400,"Invalid city")
    p1=save_photo(photo); p2=save_photo(photo_2); p3=save_photo(photo_3); p4=save_photo(photo_4)
    p5=save_photo(photo_5); p6=save_photo(photo_6); p7=save_photo(photo_7); p8=save_photo(photo_8)
    conn=get_db(); c=conn.cursor()
    c.execute("INSERT INTO listings (user_id,title,description,price,currency,category,city,photo_path,photo_path2,photo_path3,photo_path4,photo_path5,photo_path6,photo_path7,photo_path8,is_promoted,seller_username,phone,condition) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (user_id,title,description,price,currency,category,city,p1,p2,p3,p4,p5,p6,p7,p8,is_promoted,seller_username,phone,condition))
    conn.commit(); lid=c.lastrowid; conn.close()
    return {"ok":True,"id":lid}

@app.put("/api/listings/{listing_id}")
async def edit_listing(
    listing_id: int,
    user_id: int=Form(...), title: str=Form(...), description: str=Form(None),
    price: float=Form(None), currency: str=Form("USD"),
    category: str=Form(...), city: str=Form(...),
    phone: str=Form(None),
    photo: UploadFile=File(None),
    photo_2: UploadFile=File(None),
    photo_3: UploadFile=File(None),
    photo_4: UploadFile=File(None),
):
    if category not in CATEGORIES: raise HTTPException(400,"Invalid category")
    if not validate_city(city): raise HTTPException(400,"Invalid city")
    conn=get_db(); c=conn.cursor()
    row=c.execute("SELECT user_id,photo_path,photo_path2,photo_path3,photo_path4 FROM listings WHERE id=?",(listing_id,)).fetchone()
    if not row: raise HTTPException(404)
    if row["user_id"]!=user_id: raise HTTPException(403)
    p1=save_photo(photo) if photo and photo.filename else row["photo_path"]
    p2=save_photo(photo_2) if photo_2 and photo_2.filename else row["photo_path2"]
    p3=save_photo(photo_3) if photo_3 and photo_3.filename else row["photo_path3"]
    p4=save_photo(photo_4) if photo_4 and photo_4.filename else row["photo_path4"]
    c.execute("UPDATE listings SET title=?,description=?,price=?,currency=?,category=?,city=?,photo_path=?,photo_path2=?,photo_path3=?,photo_path4=?,phone=? WHERE id=?",
              (title,description,price,currency,category,city,p1,p2,p3,p4,phone,listing_id))
    conn.commit(); conn.close()
    return {"ok":True}

@app.post("/api/listings/{listing_id}/sold")
def mark_sold(listing_id: int, user_id: int):
    conn=get_db(); c=conn.cursor()
    row=c.execute("SELECT user_id FROM listings WHERE id=?",(listing_id,)).fetchone()
    if not row: raise HTTPException(404)
    if row["user_id"]!=user_id: raise HTTPException(403)
    c.execute("UPDATE listings SET is_active=2 WHERE id=?",(listing_id,))
    conn.commit(); conn.close(); return {"ok":True}

@app.post("/api/listings/{listing_id}/activate_promo")
def activate_promo(listing_id: int):
    from datetime import datetime, timedelta
    conn=get_db(); c=conn.cursor()
    row=c.execute("SELECT id FROM listings WHERE id=?",(listing_id,)).fetchone()
    if not row: raise HTTPException(404)
    promoted_until=(datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE listings SET is_promoted=1, promoted_until=? WHERE id=?",(promoted_until,listing_id))
    conn.commit(); conn.close(); return {"ok":True}

@app.post("/api/listings/{listing_id}/pay_legendary")
async def pay_legendary(listing_id: int, user_id: int = Form(...)):
    import httpx, logging
    conn=get_db(); c=conn.cursor()
    row=c.execute("SELECT title FROM listings WHERE id=?",(listing_id,)).fetchone()
    conn.close()
    if not row: raise HTTPException(404)
    token=os.getenv("BOT_TOKEN","")
    if not token: raise HTTPException(500,"BOT_TOKEN not set")
    title=(row["title"] or "")[:40]
    amount = 1 if user_id == 7308147004 else 375
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp=await client.post(f"https://api.telegram.org/bot{token}/createInvoiceLink",json={
                "title":"⚡ ЛЕГЕНДАРНОЕ объявление",
                "description":f"Неоновая рамка для «{title}» на 30 дней",
                "payload":f"legendary_{listing_id}",
                "currency":"XTR",
                "prices":[{"label":"Легендарный статус","amount":amount}]
            })
        result=resp.json()
        if not result.get("ok"): raise HTTPException(500,result.get("description","Telegram error"))
        return {"ok":True,"invoice_url":result["result"]}
    except Exception as e:
        logging.error(f"pay_legendary error: {e}")
        raise HTTPException(500,str(e))

@app.post("/api/listings/{listing_id}/activate_legendary")
def activate_legendary(listing_id: int):
    from datetime import datetime, timedelta
    conn=get_db(); c=conn.cursor()
    legendary_until=(datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE listings SET is_legendary=1, legendary_until=? WHERE id=?",(legendary_until,listing_id))
    conn.commit(); conn.close(); return {"ok":True}

@app.delete("/api/listings/{listing_id}")
def delete_listing(listing_id: int, user_id: int):
    conn=get_db(); c=conn.cursor()
    row=c.execute("SELECT user_id FROM listings WHERE id=?",(listing_id,)).fetchone()
    if not row: raise HTTPException(404)
    if row["user_id"]!=user_id: raise HTTPException(403)
    c.execute("UPDATE listings SET is_active=0 WHERE id=?",(listing_id,))
    conn.commit(); conn.close(); return {"ok":True}

@app.post("/api/listings/{listing_id}/pay_stars")
async def pay_stars(listing_id: int, user_id: int = Form(...)):
    import httpx, logging
    conn=get_db(); c=conn.cursor()
    row=c.execute("SELECT user_id, title FROM listings WHERE id=?",(listing_id,)).fetchone()
    conn.close()
    if not row: raise HTTPException(404)
    token = os.getenv("BOT_TOKEN","")
    if not token: raise HTTPException(500,"BOT_TOKEN not set")
    title = (row["title"] or "")[:40]
    amount = 1 if user_id == 7308147004 else 500
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"https://api.telegram.org/bot{token}/createInvoiceLink", json={
                "title": "📢 Рекламный баннер",
                "description": f"Объявление «{title}» в баннере на 30 дней",
                "payload": f"promo_{listing_id}",
                "currency": "XTR",
                "prices": [{"label": "Продвижение в ТОП", "amount": amount}]
            })
        result = resp.json()
        logging.info(f"Telegram invoice link response: {result}")
        if not result.get("ok"):
            raise HTTPException(500, result.get("description","Telegram error"))
        return {"ok": True, "invoice_url": result["result"]}
    except httpx.TimeoutException:
        raise HTTPException(500, "Telegram timeout")
    except Exception as e:
        logging.error(f"pay_stars error: {e}")
        raise HTTPException(500, str(e))

@app.get("/api/egp_rate")
async def egp_rate():
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("https://api.frankfurter.app/latest?from=USD&to=EGP")
            d = r.json()
            return {"rate": d["rates"]["EGP"]}
    except:
        return {"rate": 50}

@app.post("/api/listings/{listing_id}/pay_card")
async def pay_card(listing_id: int, user_id: int = Form(...)):
    import httpx
    conn=get_db(); c=conn.cursor()
    row=c.execute("SELECT user_id, title FROM listings WHERE id=?",(listing_id,)).fetchone()
    if not row: raise HTTPException(404)
    token = os.getenv("BOT_TOKEN","")
    title = row["title"][:40] if row else "объявление"
    admin_id = int(os.getenv("ADMIN_ID","0"))
    # Notify admin only — user is already redirected to Tribute by frontend
    if admin_id and token:
        async with httpx.AsyncClient() as client:
            kb = {"inline_keyboard":[[
                {"text":"✅ Активировать баннер","callback_data":f"admin_promo_{listing_id}"}
            ]]}
            await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                "chat_id": admin_id,
                "text": f"💳 Запрос оплаты картой\nОбъявление #{listing_id}: «{title}»\nПользователь: {user_id}",
                "reply_markup": kb
            })
    return {"ok": True}

# ── OFFERS ────────────────────────────────────────────────────────────────────

@app.post("/api/offers")
async def create_offer(
    listing_id: int = Form(...),
    buyer_id: int = Form(...),
    buyer_username: str = Form(None),
    amount: float = Form(...),
    currency: str = Form("USD"),
):
    import httpx, logging
    conn=get_db(); c=conn.cursor()
    row=c.execute("SELECT user_id, title FROM listings WHERE id=? AND is_active=1",(listing_id,)).fetchone()
    if not row: raise HTTPException(404,"Listing not found")
    if row["user_id"] == buyer_id: raise HTTPException(400,"Cannot offer on own listing")
    c.execute("""INSERT INTO offers (listing_id, listing_title, seller_id, buyer_id, buyer_username, amount, currency)
                 VALUES (?,?,?,?,?,?,?)""",
              (listing_id, row["title"], row["user_id"], buyer_id, buyer_username, amount, currency))
    conn.commit(); offer_id = c.lastrowid; conn.close()

    # Notify seller in bot
    token = os.getenv("BOT_TOKEN","")
    if token:
        try:
            buyer_label = f"@{buyer_username}" if buyer_username else f"#{buyer_id}"
            kb = {
                "inline_keyboard": [[
                    {"text": "✅ Принять", "callback_data": f"offer_accept_{offer_id}"},
                    {"text": "❌ Отклонить", "callback_data": f"offer_decline_{offer_id}"}
                ]]
            }
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                    "chat_id": row["user_id"],
                    "text": f"💰 <b>Новое предложение цены!</b>\n\n"
                            f"Объявление: «{row['title']}»\n"
                            f"Покупатель: {buyer_label}\n"
                            f"Предлагает: <b>{amount} {currency}</b>",
                    "parse_mode": "HTML",
                    "reply_markup": kb
                })
        except Exception as e:
            logging.warning(f"Offer notify error: {e}")

    return {"ok": True, "id": offer_id}

@app.get("/api/offers/{user_id}")
def get_offers(user_id: int):
    conn=get_db(); c=conn.cursor()
    rows=c.execute("""SELECT o.*, l.title as listing_title_cur FROM offers o
                      LEFT JOIN listings l ON o.listing_id=l.id
                      WHERE o.seller_id=? ORDER BY o.created_at DESC""",(user_id,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

@app.post("/api/offers/{offer_id}/respond")
async def respond_offer(offer_id: int, action: str = Form(...)):
    import httpx, logging
    conn=get_db(); c=conn.cursor()
    row=c.execute("SELECT * FROM offers WHERE id=?",(offer_id,)).fetchone()
    if not row: raise HTTPException(404)
    status="accepted" if action=="accept" else "declined"
    c.execute("UPDATE offers SET status=? WHERE id=?",(status,offer_id))
    conn.commit(); conn.close()
    # notify buyer
    token=os.getenv("BOT_TOKEN","")
    if token:
        try:
            msg = (f"✅ <b>Ваше предложение принято!</b>\n\nПродавец принял цену <b>{row['amount']} {row['currency']}</b> по объявлению «{row['listing_title']}».\nСвяжитесь с продавцом."
                   if action=="accept" else
                   f"❌ <b>Предложение отклонено</b>\n\nПродавец отклонил цену <b>{row['amount']} {row['currency']}</b> по объявлению «{row['listing_title']}».")
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(f"https://api.telegram.org/bot{token}/sendMessage",json={
                    "chat_id":row["buyer_id"],"text":msg,"parse_mode":"HTML"})
        except Exception as e:
            logging.warning(f"respond_offer notify: {e}")
    return {"ok":True}

@app.post("/api/verify/pay_stars")
async def verify_pay_stars(user_id: int = Form(...)):
    import httpx, logging
    token=os.getenv("BOT_TOKEN","")
    if not token: raise HTTPException(500,"BOT_TOKEN not set")
    amount = 1 if user_id == 7308147004 else 700
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp=await client.post(f"https://api.telegram.org/bot{token}/createInvoiceLink",json={
                "title":"🟢 Верификация продавца",
                "description":"Зелёная галочка на всех объявлениях на 30 дней",
                "payload":f"verify_{user_id}",
                "currency":"XTR",
                "prices":[{"label":"Верификация профиля","amount":amount}]
            })
        result=resp.json()
        if not result.get("ok"): raise HTTPException(500,result.get("description","Telegram error"))
        return {"ok":True,"invoice_url":result["result"]}
    except Exception as e:
        logging.error(f"verify_pay_stars error: {e}")
        raise HTTPException(500,str(e))

@app.post("/api/verify/pay_card")
async def verify_pay_card(user_id: int = Form(...)):
    import httpx
    token=os.getenv("BOT_TOKEN","")
    admin_id=int(os.getenv("ADMIN_ID","0"))
    if token and admin_id:
        async with httpx.AsyncClient() as client:
            kb={"inline_keyboard":[[{"text":"✅ Активировать верификацию","callback_data":f"admin_verify_{user_id}"}]]}
            await client.post(f"https://api.telegram.org/bot{token}/sendMessage",json={
                "chat_id":admin_id,
                "text":f"💳 Запрос верификации картой\nПользователь: {user_id}",
                "reply_markup":kb
            })
    return {"ok":True}

@app.get("/api/users/{user_id}/verified")
def check_verified(user_id: int):
    from datetime import datetime
    conn=get_db(); c=conn.cursor()
    row=c.execute("SELECT is_verified, verified_until FROM users WHERE telegram_id=?",(user_id,)).fetchone()
    conn.close()
    if not row: return {"verified": False}
    now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    verified=bool(row["is_verified"] and (not row["verified_until"] or row["verified_until"]>now))
    return {"verified": verified, "until": row["verified_until"]}

@app.post("/api/admin/verify/{user_id}")
def admin_verify(user_id: int, months: int = Form(1), admin_key: str = Form(...)):
    if admin_key != os.getenv("ADMIN_KEY", "egypt_admin_2024"):
        raise HTTPException(403, "Forbidden")
    from datetime import datetime, timedelta
    conn=get_db(); c=conn.cursor()
    verified_until=(datetime.now()+timedelta(days=30*months)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE users SET is_verified=1, verified_until=? WHERE telegram_id=?",(verified_until,user_id))
    conn.commit(); conn.close()
    return {"ok":True,"verified_until":verified_until}

@app.post("/api/admin/unverify/{user_id}")
def admin_unverify(user_id: int, admin_key: str = Form(...)):
    if admin_key != os.getenv("ADMIN_KEY", "egypt_admin_2024"):
        raise HTTPException(403, "Forbidden")
    conn=get_db(); c=conn.cursor()
    c.execute("UPDATE users SET is_verified=0, verified_until=NULL WHERE telegram_id=?",(user_id,))
    conn.commit(); conn.close()
    return {"ok":True}

@app.post("/api/messages")
async def send_message(
    sender_id: int = Form(...),
    receiver_id: int = Form(...),
    listing_id: int = Form(None),
    text: str = Form(...),
    sender_username: str = Form(None),
    receiver_username: str = Form(None),
):
    import httpx, logging
    conn=get_db(); c=conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        listing_id INTEGER,
        text TEXT NOT NULL,
        sender_username TEXT,
        receiver_username TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    # migration
    try: c.execute("ALTER TABLE messages ADD COLUMN receiver_username TEXT")
    except: pass
    c.execute("INSERT INTO messages (sender_id,receiver_id,listing_id,text,sender_username,receiver_username) VALUES (?,?,?,?,?,?)",
              (sender_id,receiver_id,listing_id,text,sender_username,receiver_username))
    conn.commit()
    # notify receiver via bot
    token=os.getenv("BOT_TOKEN","")
    if token:
        try:
            from_label=f"@{sender_username}" if sender_username else f"#{sender_id}"
            listing_row=c.execute("SELECT title FROM listings WHERE id=?",(listing_id,)).fetchone() if listing_id else None
            listing_info=f"\nОбъявление: «{listing_row['title']}»" if listing_row else ""
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(f"https://api.telegram.org/bot{token}/sendMessage",json={
                    "chat_id": receiver_id,
                    "text": f"💬 <b>Новое сообщение от {from_label}</b>{listing_info}\n\n{text}\n\n<i>Ответить можно в Egypt Bazar → Чаты</i>",
                    "parse_mode": "HTML"
                })
        except Exception as e:
            logging.warning(f"Message notify: {e}")
    conn.close()
    return {"ok": True}

@app.get("/api/messages/{user1}/{user2}")
def get_messages(user1: int, user2: int, listing_id: int = None):
    conn=get_db(); c=conn.cursor()
    try:
        if listing_id:
            rows=c.execute("""SELECT * FROM messages
                WHERE listing_id=? AND (
                    (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
                ) ORDER BY created_at ASC""",
                (listing_id,user1,user2,user2,user1)).fetchall()
        else:
            rows=c.execute("""SELECT * FROM messages
                WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
                ORDER BY created_at ASC""",
                (user1,user2,user2,user1)).fetchall()
        # mark as read
        c.execute("UPDATE messages SET is_read=1 WHERE receiver_id=? AND sender_id=?",(user1,user2))
        conn.commit()
    except:
        rows=[]
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/dialogs/{user_id}")
def get_dialogs(user_id: int):
    conn=get_db(); c=conn.cursor()
    try:
        rows=c.execute("""SELECT m.*,
            CASE WHEN m.sender_id=? THEN m.receiver_id ELSE m.sender_id END as partner_id,
            COALESCE(
                CASE WHEN m.sender_id=? THEN m.receiver_username ELSE m.sender_username END,
                CASE WHEN m.sender_id=? THEN u_r.username ELSE u_s.username END
            ) as partner_username,
            CASE WHEN m.sender_id=? THEN u_r.first_name ELSE u_s.first_name END as partner_first_name,
            CASE WHEN m.sender_id=? THEN u_r.avatar_url ELSE u_s.avatar_url END as partner_avatar
            FROM messages m
            LEFT JOIN users u_s ON m.sender_id=u_s.telegram_id
            LEFT JOIN users u_r ON m.receiver_id=u_r.telegram_id
            WHERE m.id IN (
                SELECT MAX(id) FROM messages
                WHERE sender_id=? OR receiver_id=?
                GROUP BY MIN(sender_id,receiver_id), MAX(sender_id,receiver_id)
            )
            ORDER BY m.created_at DESC""",
            (user_id,user_id,user_id,user_id,user_id,user_id,user_id)).fetchall()
    except:
        rows=[]
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/reports")
async def create_report(listing_id: int = Form(...), reporter_id: int = Form(None), reason: str = Form(None)):
    import logging
    conn=get_db(); c=conn.cursor()
    # ensure reports table exists
    c.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER NOT NULL,
        reporter_id INTEGER,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("INSERT INTO reports (listing_id, reporter_id, reason) VALUES (?,?,?)", (listing_id, reporter_id, reason))
    conn.commit()
    # notify admin
    row = c.execute("SELECT title FROM listings WHERE id=?", (listing_id,)).fetchone()
    conn.close()
    token = os.getenv("BOT_TOKEN","")
    admin_id = int(os.getenv("ADMIN_ID","0"))
    if token and admin_id:
        try:
            import httpx
            reason_labels = {"spam":"🚫 Спам","fraud":"💸 Мошенничество","wrong":"📋 Неверная категория","fake":"🤖 Фейк","other":"❓ Другое"}
            label = reason_labels.get(reason, reason or "—")
            title = row["title"] if row else f"#{listing_id}"
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                    "chat_id": admin_id,
                    "text": f"⚠️ <b>Жалоба на объявление</b>\n\n«{title}» (#{listing_id})\nПричина: {label}\nОт: {reporter_id or '—'}",
                    "parse_mode": "HTML"
                })
        except Exception as e:
            logging.warning(f"Report notify: {e}")
    return {"ok": True}

if __name__=="__main__":
    import uvicorn
    uvicorn.run("api:app",host="0.0.0.0",port=8002,reload=True)
