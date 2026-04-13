import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command

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


@dp.message(CommandStart())
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 Open Bazar", web_app=WebAppInfo(url=WEBAPP_URL)),
            InlineKeyboardButton(text="💬 Community", url=COMMUNITY_URL)
        ]
    ])
    await message.answer(
        "🌴 <b>Добро пожаловать в Egypt Bazar!</b>\n\n"
        "Покупай и продавай в Шарм-эль-Шейхе, Хургаде и других городах Египта.\n\n"
        "Нажми кнопку ниже 👇",
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


async def main():
    init_db()
    asyncio.create_task(check_expiring())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
