import os
import logging
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

import aiosqlite

# === Налаштування ===
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TOKEN")
ADMIN_ID = 685834441  # ← твій ID, зміни якщо треба

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DB_NAME = "users.db"

# === База даних ===
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance INTEGER DEFAULT 0,
                ref_count INTEGER DEFAULT 0,
                deep_link TEXT,
                registered_at TEXT
            )
        ''')
        await db.commit()

async def get_or_create_user(user: types.User, referrer_id: int = None):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user.id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([c[0] for c in cursor.description], row))

        deep_link = f"ref{user.id}"
        async with db.execute(
            "INSERT INTO users (user_id, username, first_name, deep_link, registered_at) VALUES (?, ?, ?, ?, ?)",
            (user.id, user.username or "", user.first_name or "", deep_link, datetime.now().isoformat())
        ) as cursor:
            await db.commit()

        # нарахування рефералу
        if referrer_id and referrer_id != user.id:
            await db.execute("UPDATE users SET ref_count = ref_count + 1, balance = balance + 5000 WHERE user_id = ?", (referrer_id,))
            await db.commit()
            try:
                await bot.send_message(referrer_id, "✨ Новий реферал! +5000 монет на баланс!")
            except:
                pass

        return {
            "user_id": user.id,
            "username": user.username or "",
            "first_name": user.first_name or "",
            "balance": 0,
            "ref_count": 0,
            "deep_link": deep_link
        }

# === Клавіатура ===
main_kb = types.ReplyKeyboardMarkup(keyboard=[
    [types.KeyboardButton(text="Мій баланс")],
    [types.KeyboardButton(text="Рефералка"), types.KeyboardButton(text="Топ")]
], resize_keyboard=True)

# === Хендлери ===
@dp.message(CommandStart(deep_link=True))
async def start_ref(message: types.Message):
    args = message.text.split(maxsplit=1)
    referrer_id = int(args[1][3:]) if len(args) > 1 and args[1].startswith("ref") else None
    user = await get_or_create_user(message.from_user, referrer_id)
    await message.answer(
        f"Привіт, <b>{message.from_user.first_name}</b>!\n\n"
        "Твій баланс: <b>0</b> монет\n"
        "Запрошуй друзів — за кожного +5000 монет!",
        reply_markup=main_kb
    )

@dp.message(CommandStart())
async def start(message: types.Message):
    await start_ref(message)

@dp.message(lambda m: m.text == "Мій баланс")
async def balance(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance, ref_count FROM users WHERE user_id = ?", (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                bal, ref_count = row
                await message.answer(f"<b>Твій баланс:</b> {bal:,} монет\n<b>Запрошено друзів:</b> {ref_count}", reply_markup=main_kb)

@dp.message(lambda m: m.text == "Рефералка")
async def referral(message: types.Message):
    link = f"https://t.me/{(await bot.get_me()).username}?start=ref{message.from_user.id}"
    await message.answer(
        "<b>Твоя реферальна ссылка</b>\n\n"
        f"<code>{link}</code>\n\n"
        "За кожного друга — <b>+5000 монет</b> тобі!",
        reply_markup=main_kb
    )

@dp.message(Command("stats"))
async def stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*), SUM(ref_count) FROM users") as cursor:
            total_users, total_refs = (await cursor.fetchone())
        await message.answer(f"<b>Статистика бота</b>\n\nПользователі: {total_users}\nПриглашено: {total_refs or 0}")

# === Запуск ===
async def main():
    await init_db()
    logging.info("Бот запущений — база + рефералка готові!")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
