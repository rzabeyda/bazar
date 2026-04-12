import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv
from database import get_db, init_db

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://bazaregypt.store")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🛒 Открыть Egypt Bazar",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ])
    await message.answer(
        "🌴 <b>Добро пожаловать в Egypt Bazar!</b>\n\n"
        "Покупай и продавай одежду, продукты, электронику и многое другое "
        "в Шарм-эль-Шейхе, Хургаде, Каире и других городах Египта.\n\n"
        "Нажми кнопку ниже чтобы открыть маркетплейс 👇",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("extend_"))
async def extend_listing(call: types.CallbackQuery):
    listing_id = int(call.data.split("_")[1])
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT user_id, title FROM listings WHERE id=? AND is_active=1", (listing_id,)).fetchone()
    if not row or row["user_id"] != call.from_user.id:
        await call.answer("Объявление не найдено", show_alert=True)
        conn.close(); return
    new_expires = datetime.now() + timedelta(days=30)
    c.execute("UPDATE listings SET expires_at=?, notified_expiry=0 WHERE id=?",
              (new_expires.strftime("%Y-%m-%d %H:%M:%S"), listing_id))
    conn.commit(); conn.close()
    await call.answer("✅ Объявление продлено на 30 дней!")
    await call.message.edit_text(
        f"✅ <b>Объявление продлено!</b>\n\n"
        f"«{row['title']}» будет активно ещё 30 дней.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("delete_"))
async def delete_listing(call: types.CallbackQuery):
    listing_id = int(call.data.split("_")[1])
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT user_id, title FROM listings WHERE id=?", (listing_id,)).fetchone()
    if not row or row["user_id"] != call.from_user.id:
        await call.answer("Объявление не найдено", show_alert=True)
        conn.close(); return
    c.execute("UPDATE listings SET is_active=0 WHERE id=?", (listing_id,))
    conn.commit(); conn.close()
    await call.answer("🗑 Удалено")
    await call.message.edit_text(f"🗑 Объявление «{row['title']}» удалено.")


async def check_expiring():
    """Run daily: notify users 3 days before expiry, deactivate expired."""
    while True:
        await asyncio.sleep(86400)  # every 24h
        conn = get_db(); c = conn.cursor()
        now = datetime.now()
        warn_threshold = now + timedelta(days=3)

        # Notify about expiring (3 days left, not yet notified)
        expiring = c.execute("""
            SELECT id, user_id, title FROM listings
            WHERE is_active=1 AND notified_expiry=0
            AND expires_at <= ? AND expires_at > ?
        """, (warn_threshold.strftime("%Y-%m-%d %H:%M:%S"),
              now.strftime("%Y-%m-%d %H:%M:%S"))).fetchall()

        for l in expiring:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Продлить на 30 дней", callback_data=f"extend_{l['id']}")],
                [InlineKeyboardButton(text="🗑 Удалить объявление", callback_data=f"delete_{l['id']}")]
            ])
            try:
                await bot.send_message(
                    l["user_id"],
                    f"⏰ <b>Ваше объявление скоро истечёт!</b>\n\n"
                    f"«{l['title']}» будет деактивировано через 3 дня.\n\n"
                    f"Хотите продлить его ещё на 30 дней?",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                c.execute("UPDATE listings SET notified_expiry=1 WHERE id=?", (l["id"],))
            except Exception as e:
                logging.warning(f"Could not notify user {l['user_id']}: {e}")

        # Deactivate expired
        c.execute("""
            UPDATE listings SET is_active=0
            WHERE is_active=1 AND expires_at <= ?
        """, (now.strftime("%Y-%m-%d %H:%M:%S"),))

        conn.commit(); conn.close()
        logging.info(f"Expiry check done: {len(expiring)} notified")


async def main():
    init_db()
    asyncio.create_task(check_expiring())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
