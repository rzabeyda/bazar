import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    LabeledPrice, PreCheckoutQuery
)
from dotenv import load_dotenv
from database import get_db, init_db

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://bazaregypt.store")
TON_WALLET = "UQDngkmwbJxausCBgrbXcS_LmQYtGLG0-qfsaCYijyczQVap"
TRIBUTE_URL = "https://t.me/tribute/app?startapp=diuS"
COMMUNITY_URL = "https://t.me/egypt_links"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("verify"))
async def cmd_verify(message: types.Message):
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if message.from_user.id != admin_id:
        return
    # /verify 123456789 3  (user_id, months)
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /verify USER_ID [месяцев]\nПример: /verify 123456789 1")
        return
    user_id = int(parts[1])
    months = int(parts[2]) if len(parts) > 2 else 1
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.post(f"http://localhost:8002/api/admin/verify/{user_id}",
            data={"months": months, "admin_key": "egypt_admin_2024"})
    if r.json().get("ok"):
        await message.answer(f"✅ Пользователь {user_id} верифицирован на {months} мес.\nДо: {r.json()['verified_until']}")
        try:
            await bot.send_message(user_id,
                "✅ <b>Вы получили верификацию Egypt Bazar!</b>\n\nЗелёная галочка теперь видна на всех ваших объявлениях.",
                parse_mode="HTML")
        except: pass
    else:
        await message.answer("❌ Ошибка верификации")

@dp.message(Command("unverify"))
async def cmd_unverify(message: types.Message):
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if message.from_user.id != admin_id: return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /unverify USER_ID")
        return
    user_id = int(parts[1])
    import httpx
    async with httpx.AsyncClient() as client:
        await client.post(f"http://localhost:8002/api/admin/unverify/{user_id}",
            data={"admin_key": "egypt_admin_2024"})
    await message.answer(f"✅ Верификация снята с {user_id}")



@dp.message(CommandStart())
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 Open Bazar", web_app=WebAppInfo(url=WEBAPP_URL)),
            InlineKeyboardButton(text="💬 Community", url=COMMUNITY_URL)
        ]
    ])
    # Save user + try to get avatar
    try:
        from database import get_db
        user = message.from_user
        # Get profile photo
        avatar_url = None
        try:
            photos = await bot.get_user_profile_photos(user.id, limit=1)
            if photos.photos:
                file = await bot.get_file(photos.photos[0][-1].file_id)
                avatar_url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file.file_path}"
        except: pass
        conn = get_db(); c = conn.cursor()
        # Add avatar_url column if not exists
        try: c.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
        except: pass
        c.execute("""INSERT INTO users (telegram_id,username,first_name,avatar_url)
            VALUES (?,?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET
            username=excluded.username,first_name=excluded.first_name,
            avatar_url=COALESCE(excluded.avatar_url,avatar_url)""",
            (user.id, user.username, user.first_name, avatar_url))
        conn.commit(); conn.close()
    except Exception as e:
        logging.warning(f"start save user: {e}")
    try:
        photo = types.FSInputFile("/root/bazar/static/icons/hey.png")
        await message.answer_photo(
            photo=photo,
            caption="🌴 <b>Добро пожаловать в Egypt Bazar!</b>\n"
                    "Покупай и продавай в Шарм-эль-Шейхе, Хургаде и других городах Египта.\n\n"
                    "🌴 <b>Welcome to Egypt Bazar!</b>\n"
                    "Buy and sell in Sharm el-Sheikh, Hurghada and other cities of Egypt.",
            parse_mode="HTML", reply_markup=keyboard
        )
    except Exception as e:
        logging.warning(f"start photo error: {e}")
        await message.answer(
            "🌴 <b>Добро пожаловать в Egypt Bazar!</b>\n"
            "Покупай и продавай в Шарм-эль-Шейхе, Хургаде и других городах Египта.\n\n"
            "🌴 <b>Welcome to Egypt Bazar!</b>\n"
            "Buy and sell in Sharm el-Sheikh, Hurghada and other cities of Egypt.",
            parse_mode="HTML", reply_markup=keyboard
        )


# ── STARS ─────────────────────────────────────────────────────────────────────

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    conn = get_db(); c = conn.cursor()

    if payload.startswith("promo_"):
        listing_id = int(payload.split("_")[1])
        row = c.execute("SELECT title FROM listings WHERE id=?", (listing_id,)).fetchone()
        promoted_until = (datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE listings SET is_promoted=1, is_active=1, promoted_until=? WHERE id=?", (promoted_until, listing_id))
        conn.commit(); conn.close()
        title = row["title"] if row else "объявление"
        await message.answer(f"✅ <b>Баннер активирован!</b>\n\n«{title}» в баннере 30 дней.", parse_mode="HTML")

    elif payload.startswith("legendary_"):
        listing_id = int(payload.split("_")[1])
        row = c.execute("SELECT title FROM listings WHERE id=?", (listing_id,)).fetchone()
        legendary_until = (datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE listings SET is_legendary=1, legendary_until=? WHERE id=?", (legendary_until, listing_id))
        conn.commit(); conn.close()
        title = row["title"] if row else "объявление"
        await message.answer(f"⚡ <b>ЛЕГЕНДАРНОЕ активировано!</b>\n\n«{title}» с неоновой рамкой 30 дней.", parse_mode="HTML")
    elif payload.startswith("verify_"):
        user_id_v = int(payload.split("_")[1])
        from datetime import datetime, timedelta
        verified_until=(datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE users SET is_verified=1, verified_until=? WHERE telegram_id=?",(verified_until,user_id_v))
        conn.commit(); conn.close()
        await message.answer("🟢 <b>Верификация активирована!</b>\n\nЗелёная галочка появится на всех ваших объявлениях.", parse_mode="HTML")
    else:
        conn.close()


# ── TON/USDT ──────────────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("ton_confirm_"))
async def ton_confirm(call: types.CallbackQuery):
    listing_id = int(call.data.split("_")[2])
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT title FROM listings WHERE id=?", (listing_id,)).fetchone()
    conn.close()
    title = row["title"] if row else "объявление"
    await call.answer("✅ Запрос отправлен!")
    await call.message.edit_text(
        f"⏳ Запрос на активацию баннера для «{title}» отправлен. Обычно до 1 часа.",
        parse_mode="HTML"
    )
    try:
        admin_id = int(os.getenv("ADMIN_ID", "0"))
        if admin_id:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Активировать", callback_data=f"admin_promo_{listing_id}")]
            ])
            await bot.send_message(
                admin_id,
                f"💎 TON оплата!\n"
                f"Юзер: @{call.from_user.username or call.from_user.id}\n"
                f"Объявление #{listing_id}: «{title}»\n"
                f"Кошелёк: <code>{TON_WALLET}</code>",
                parse_mode="HTML", reply_markup=kb
            )
    except Exception as e:
        logging.warning(f"Admin notify: {e}")


@dp.callback_query(F.data.startswith("admin_promo_"))
async def admin_activate_promo(call: types.CallbackQuery):
    listing_id = int(call.data.split("_")[2])
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT user_id, title FROM listings WHERE id=?", (listing_id,)).fetchone()
    promoted_until = (datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE listings SET is_promoted=1, is_active=1, promoted_until=? WHERE id=?", (promoted_until, listing_id))
    conn.commit(); conn.close()
    await call.answer("✅ Активировано!")
    await call.message.edit_text(f"✅ Баннер активирован #{listing_id}")
    if row:
        await bot.send_message(row["user_id"],
            f"✅ Баннер для «{row['title']}» активирован на 30 дней!", parse_mode="HTML")


# ── OFFER PRICE ───────────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("offer_accept_"))
async def offer_accept(call: types.CallbackQuery):
    offer_id = int(call.data.split("_")[2])
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT * FROM offers WHERE id=?", (offer_id,)).fetchone()
    if not row:
        await call.answer("Не найдено", show_alert=True); conn.close(); return
    c.execute("UPDATE offers SET status='accepted' WHERE id=?", (offer_id,))
    conn.commit(); conn.close()
    await call.answer("✅ Принято!")
    await call.message.edit_text(
        call.message.text + "\n\n✅ <b>Вы приняли предложение!</b>",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(
            row["buyer_id"],
            f"✅ <b>Ваше предложение принято!</b>\n\n"
            f"Продавец принял вашу цену <b>{row['amount']} {row['currency']}</b> по объявлению «{row['listing_title']}».\n"
            f"Свяжитесь с продавцом для завершения сделки.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Offer accept notify: {e}")


@dp.callback_query(F.data.startswith("offer_decline_"))
async def offer_decline(call: types.CallbackQuery):
    offer_id = int(call.data.split("_")[2])
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT * FROM offers WHERE id=?", (offer_id,)).fetchone()
    if not row:
        await call.answer("Не найдено", show_alert=True); conn.close(); return
    c.execute("UPDATE offers SET status='declined' WHERE id=?", (offer_id,))
    conn.commit(); conn.close()
    await call.answer("❌ Отклонено")
    await call.message.edit_text(
        call.message.text + "\n\n❌ <b>Вы отклонили предложение.</b>",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(
            row["buyer_id"],
            f"❌ <b>Предложение отклонено</b>\n\n"
            f"Продавец отклонил вашу цену <b>{row['amount']} {row['currency']}</b> по объявлению «{row['listing_title']}».",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Offer decline notify: {e}")


# ── EXTEND / DELETE ───────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("admin_verify_"))
async def admin_activate_verify(call: types.CallbackQuery):
    user_id_v = int(call.data.split("_")[2])
    conn = get_db(); c = conn.cursor()
    verified_until=(datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE users SET is_verified=1, verified_until=? WHERE telegram_id=?",(verified_until,user_id_v))
    conn.commit(); conn.close()
    await call.answer("✅ Верификация активирована!")
    await call.message.edit_text(f"✅ Верификация активирована для {user_id_v}")
    try:
        await bot.send_message(user_id_v,"🟢 <b>Верификация активирована!</b>\n\nЗелёная галочка появится на всех ваших объявлениях.",parse_mode="HTML")
    except: pass
async def extend_listing(call: types.CallbackQuery):
    listing_id = int(call.data.split("_")[1])
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT user_id, title FROM listings WHERE id=? AND is_active=1", (listing_id,)).fetchone()
    if not row or row["user_id"] != call.from_user.id:
        await call.answer("Не найдено", show_alert=True); conn.close(); return
    new_expires = datetime.now() + timedelta(days=30)
    c.execute("UPDATE listings SET expires_at=?, notified_expiry=0 WHERE id=?",
              (new_expires.strftime("%Y-%m-%d %H:%M:%S"), listing_id))
    conn.commit(); conn.close()
    await call.answer("✅ Продлено на 30 дней!")
    await call.message.edit_text(f"✅ «{row['title']}» активно ещё 30 дней.", parse_mode="HTML")


@dp.callback_query(F.data.startswith("delete_"))
async def delete_listing_cb(call: types.CallbackQuery):
    listing_id = int(call.data.split("_")[1])
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT user_id, title FROM listings WHERE id=?", (listing_id,)).fetchone()
    if not row or row["user_id"] != call.from_user.id:
        await call.answer("Не найдено", show_alert=True); conn.close(); return
    c.execute("UPDATE listings SET is_active=0 WHERE id=?", (listing_id,))
    conn.commit(); conn.close()
    await call.answer("🗑 Удалено")
    await call.message.edit_text(f"🗑 «{row['title']}» удалено.")


# ── EXPIRY CHECK ──────────────────────────────────────────────────────────────

async def check_expiring():
    while True:
        await asyncio.sleep(3600)
        conn = get_db(); c = conn.cursor()
        now = datetime.now()

        c.execute("""
            UPDATE listings SET is_promoted=0
            WHERE is_promoted=1 AND promoted_until IS NOT NULL AND promoted_until <= ?
        """, (now.strftime("%Y-%m-%d %H:%M:%S"),))

        c.execute("""
            UPDATE listings SET is_legendary=0
            WHERE is_legendary=1 AND legendary_until IS NOT NULL AND legendary_until <= ?
        """, (now.strftime("%Y-%m-%d %H:%M:%S"),))

        warn_threshold = now + timedelta(days=3)
        expiring = c.execute("""
            SELECT id, user_id, title FROM listings
            WHERE is_active=1 AND notified_expiry=0
            AND expires_at <= ? AND expires_at > ?
        """, (warn_threshold.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S"))).fetchall()
        for l in expiring:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Продлить на 30 дней", callback_data=f"extend_{l['id']}")],
                [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{l['id']}")]
            ])
            try:
                await bot.send_message(l["user_id"],
                    f"⏰ <b>Объявление скоро истечёт!</b>\n\n«{l['title']}» деактивируется через 3 дня.",
                    parse_mode="HTML", reply_markup=kb)
                c.execute("UPDATE listings SET notified_expiry=1 WHERE id=?", (l["id"],))
            except Exception as e:
                logging.warning(f"Notify error: {e}")
        c.execute("UPDATE listings SET is_active=0 WHERE is_active=1 AND expires_at <= ?",
                  (now.strftime("%Y-%m-%d %H:%M:%S"),))
        conn.commit(); conn.close()


@dp.message(Command("verified"))
async def cmd_verified_list(message: types.Message):
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if message.from_user.id != admin_id:
        return
    import httpx
    from database import get_db
    conn = get_db(); c = conn.cursor()
    rows = c.execute("""SELECT telegram_id, username, verified_until 
        FROM users WHERE is_verified=1 AND verified_until IS NOT NULL 
        ORDER BY verified_until ASC""").fetchall()
    conn.close()
    if not rows:
        await message.answer("Верифицированных нет.")
        return
    from datetime import datetime
    now = datetime.now()
    lines = ["<b>✅ Верифицированные пользователи:</b>\n"]
    for r in rows:
        until = datetime.strptime(r["verified_until"], "%Y-%m-%d %H:%M:%S")
        days_left = (until - now).days
        status = "🔴 истёк" if days_left < 0 else f"🟢 {days_left} дн."
        name = f"@{r['username']}" if r['username'] else f"#{r['telegram_id']}"
        lines.append(f"{name} — до {until.strftime('%d.%m.%Y')} ({status})")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def check_verify_expiring():
    """Remind users 3 days before verification expires"""
    while True:
        await asyncio.sleep(3600)
        try:
            from database import get_db
            from datetime import datetime, timedelta
            conn = get_db(); c = conn.cursor()
            now = datetime.now()
            warn = now + timedelta(days=3)
            # users expiring in 3 days
            expiring = c.execute("""SELECT telegram_id, username, verified_until FROM users
                WHERE is_verified=1 AND verified_until <= ? AND verified_until > ?""",
                (warn.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S"))).fetchall()
            for u in expiring:
                try:
                    until = datetime.strptime(u["verified_until"], "%Y-%m-%d %H:%M:%S")
                    days_left = (until - now).days
                    await bot.send_message(u["telegram_id"],
                        f"⚠️ <b>Ваша верификация истекает через {days_left} дн.</b>\n\n"
                        f"До: {until.strftime('%d.%m.%Y')}\n\n"
                        f"Продлите верификацию в профиле Egypt Bazar.",
                        parse_mode="HTML")
                except: pass
            # expired - remove verification
            c.execute("""UPDATE users SET is_verified=0 WHERE is_verified=1 
                AND verified_until IS NOT NULL AND verified_until <= ?""",
                (now.strftime("%Y-%m-%d %H:%M:%S"),))
            # notify admin about expired
            expired = c.execute("""SELECT telegram_id, username FROM users
                WHERE is_verified=0 AND verified_until IS NOT NULL 
                AND verified_until <= ? AND verified_until > ?""",
                (now.strftime("%Y-%m-%d %H:%M:%S"),
                 (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"))).fetchall()
            if expired:
                admin_id = int(os.getenv("ADMIN_ID", "0"))
                names = ", ".join([f"@{u['username']}" if u['username'] else f"#{u['telegram_id']}" for u in expired])
                try:
                    await bot.send_message(admin_id,
                        f"🔴 <b>Верификация истекла:</b> {names}",
                        parse_mode="HTML")
                except: pass
            conn.commit(); conn.close()
        except Exception as e:
            logging.warning(f"check_verify_expiring: {e}")


@dp.message(F.text & ~F.text.startswith("/"))
async def forward_to_admin(message: types.Message):
    """Forward any user message to admin so he sees replies"""
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    user = message.from_user
    # Save user to DB so their username appears in chats
    try:
        from database import get_db
        conn = get_db(); c = conn.cursor()
        c.execute("INSERT INTO users (telegram_id,username,first_name) VALUES (?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name",
                  (user.id, user.username, user.first_name))
        conn.commit(); conn.close()
    except Exception as e:
        logging.warning(f"save user: {e}")
    if not admin_id or user.id == admin_id:
        return
    name = f"@{user.username}" if user.username else f"{user.first_name or ''} #{user.id}"
    try:
        await bot.send_message(
            admin_id,
            f"💬 <b>Сообщение от {name}:</b>\n\n{message.text}",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"forward_to_admin: {e}")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if message.from_user.id != admin_id:
        return
    from database import get_db
    from datetime import datetime, timedelta
    conn = get_db(); c = conn.cursor()

    total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    new_today = c.execute("SELECT COUNT(*) FROM users WHERE date(created_at)=date('now')").fetchone()[0]
    new_week = c.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now','-7 days')").fetchone()[0]

    total_listings = c.execute("SELECT COUNT(*) FROM listings WHERE is_active=1 AND user_id!=9999999999").fetchone()[0]
    new_listings_today = c.execute("SELECT COUNT(*) FROM listings WHERE is_active=1 AND user_id!=9999999999 AND date(created_at)=date('now')").fetchone()[0]
    new_listings_week = c.execute("SELECT COUNT(*) FROM listings WHERE is_active=1 AND user_id!=9999999999 AND created_at >= datetime('now','-7 days')").fetchone()[0]

    total_messages = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    total_offers = c.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
    verified_count = c.execute("SELECT COUNT(*) FROM users WHERE is_verified=1").fetchone()[0]

    conn.close()
    await message.answer(
        f"📊 <b>Статистика Egypt Bazar</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"  Всего: <b>{total_users}</b>\n"
        f"  Сегодня: <b>+{new_today}</b>\n"
        f"  За неделю: <b>+{new_week}</b>\n"
        f"  Верифицированных: <b>{verified_count}</b>\n\n"
        f"📋 <b>Объявления (реальные):</b>\n"
        f"  Активных: <b>{total_listings}</b>\n"
        f"  Сегодня: <b>+{new_listings_today}</b>\n"
        f"  За неделю: <b>+{new_listings_week}</b>\n\n"
        f"💬 <b>Активность:</b>\n"
        f"  Сообщений: <b>{total_messages}</b>\n"
        f"  Офферов: <b>{total_offers}</b>",
        parse_mode="HTML"
    )


@dp.message(Command("new"))
async def cmd_new_listings(message: types.Message):
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if message.from_user.id != admin_id:
        return
    from database import get_db
    conn = get_db(); c = conn.cursor()
    rows = c.execute("""
        SELECT l.id, l.title, l.price, l.currency, l.category, l.city,
               u.username, u.first_name, l.created_at
        FROM listings l
        LEFT JOIN users u ON l.user_id=u.telegram_id
        WHERE l.is_active=1 AND l.user_id!=9999999999
        ORDER BY l.created_at DESC LIMIT 10
    """).fetchall()
    conn.close()
    if not rows:
        await message.answer("Новых объявлений нет.")
        return
    lines = ["📋 <b>Последние 10 объявлений:</b>\n"]
    for r in rows:
        name = f"@{r['username']}" if r['username'] else r['first_name'] or f"#{r['user_id'] if 'user_id' in r.keys() else '?'}"
        price = f"{r['price']} {r['currency']}" if r['price'] else "Договорная"
        lines.append(f"#{r['id']} <b>{r['title']}</b>\n  💰 {price} · 📍 {r['city']} · 👤 {name}")
    await message.answer("\n\n".join(lines), parse_mode="HTML")


@dp.message(Command("newusers"))
async def cmd_new_users(message: types.Message):
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if message.from_user.id != admin_id:
        return
    from database import get_db
    conn = get_db(); c = conn.cursor()
    rows = c.execute("""
        SELECT telegram_id, username, first_name, created_at
        FROM users ORDER BY created_at DESC LIMIT 15
    """).fetchall()
    conn.close()
    lines = ["👥 <b>Последние 15 пользователей:</b>\n"]
    for r in rows:
        name = f"@{r['username']}" if r['username'] else r['first_name'] or f"#{r['telegram_id']}"
        dt = r['created_at'][:10] if r['created_at'] else "?"
        lines.append(f"{name} · {dt}")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def main():
    init_db()
    asyncio.create_task(check_expiring())
    asyncio.create_task(check_verify_expiring())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
