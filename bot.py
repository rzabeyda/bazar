import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
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
PROMO_STARS = 400

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Открыть Egypt Bazar", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer(
        "🌴 <b>Добро пожаловать в Egypt Bazar!</b>\n\n"
        "Покупай и продавай в Шарм-эль-Шейхе, Хургаде и других городах Египта.\n\n"
        "Нажми кнопку ниже 👇",
        parse_mode="HTML", reply_markup=keyboard
    )


# ── STARS ─────────────────────────────────────────────────────────────────────

async def send_stars_invoice(user_id: int, listing_id: int, title: str):
    try:
        await bot.send_invoice(
            chat_id=user_id,
            title="📢 Рекламный баннер",
            description=f"Объявление «{title[:40]}» в баннере на 24 часа",
            payload=f"promo_{listing_id}",
            currency="XTR",
            prices=[LabeledPrice(label="Продвижение в ТОП", amount=PROMO_STARS)],
        )
    except Exception as e:
        logging.error(f"Invoice error: {e}")


@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    conn = get_db(); c = conn.cursor()
    from datetime import datetime, timedelta

    if payload.startswith("promo_"):
        listing_id = int(payload.split("_")[1])
        row = c.execute("SELECT title FROM listings WHERE id=?", (listing_id,)).fetchone()
        promoted_until = (datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE listings SET is_promoted=1, is_active=1, promoted_until=? WHERE id=?", (promoted_until, listing_id))
        conn.commit(); conn.close()
        title = row["title"] if row else "объявление"
        await message.answer(f"✅ <b>Баннер активирован!</b>\n\n«{title}» в баннере 15 дней.", parse_mode="HTML")

    elif payload.startswith("legendary_"):
        listing_id = int(payload.split("_")[1])
        row = c.execute("SELECT title FROM listings WHERE id=?", (listing_id,)).fetchone()
        legendary_until = (datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE listings SET is_legendary=1, legendary_until=? WHERE id=?", (legendary_until, listing_id))
        conn.commit(); conn.close()
        title = row["title"] if row else "объявление"
        await message.answer(f"⚡ <b>ЛЕГЕНДАРНОЕ активировано!</b>\n\n«{title}» с неоновой рамкой 15 дней.", parse_mode="HTML")
    else:
        conn.close()


# ── TON/USDT ──────────────────────────────────────────────────────────────────

async def send_ton_invoice(user_id: int, listing_id: int, title: str):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"ton_confirm_{listing_id}")]
    ])
    await bot.send_message(
        user_id,
        f"💎 <b>Оплата TON / USDT (сеть TON)</b>\n\n"
        f"Переведите <b>$5</b> на адрес:\n\n"
        f"<code>{TON_WALLET}</code>\n\n"
        f"Поддерживается TON и USDT в сети TON.\n"
        f"После оплаты нажмите кнопку ниже.",
        parse_mode="HTML", reply_markup=keyboard
    )


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
    from datetime import datetime, timedelta
    promoted_until=(datetime.now()+timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE listings SET is_promoted=1, is_active=1, promoted_until=? WHERE id=?", (promoted_until, listing_id))
    conn.commit(); conn.close()
    await call.answer("✅ Активировано!")
    await call.message.edit_text(f"✅ Баннер активирован #{listing_id}")
    if row:
        await bot.send_message(row["user_id"],
            f"✅ Баннер для «{row['title']}» активирован!", parse_mode="HTML")


# ── EXTEND / DELETE ───────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("extend_"))
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
        await asyncio.sleep(3600)  # every hour
        conn = get_db(); c = conn.cursor()
        now = datetime.now()
        
        # Deactivate expired banners
        c.execute("""
            UPDATE listings SET is_promoted=0
            WHERE is_promoted=1 AND promoted_until IS NOT NULL AND promoted_until <= ?
        """, (now.strftime("%Y-%m-%d %H:%M:%S"),))

        # Deactivate expired legendary
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
