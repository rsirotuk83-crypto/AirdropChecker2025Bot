import os
import asyncio
import json
import logging
import httpx
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Тепер дані зберігаються назавжди завдяки Volume
DATA_DIR = "/app/data"
DB_PATH = os.path.join(DATA_DIR, "db.json")
os.makedirs(DATA_DIR, exist_ok=True)

subs = {}
active = False
combo_text = "Комбо ще не встановлено.\nАдмін, надішли /seturl <посилання на .txt>"
source_url = ""

def load():
    global subs, active, combo_text, source_url
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
                subs = {int(k): v for k, v in d.get("subs", {}).items()}
                active = d.get("active", False)
                combo_text = d.get("combo", combo_text)
                source_url = d.get("url", "")
        except Exception as e:
            logging.error(f"Помилка читання: {e}")

def save():
    data = {"subs": subs, "active": active, "combo": combo_text, "url": source_url}
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Помилка збереження: {e}")

load()

# Автооновлення
async def fetch():
    global combo_text
    if not source_url: return
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(source_url, timeout=15)
            if r.status_code == 200:
                new = r.text.strip()
                if new != combo_text:
                    combo_text = new
                    save()
                    await bot.send_message(ADMIN_ID, "Комбо автоматично оновлено!")
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"Помилка автооновлення:\n{e}")

async def scheduler():
    await asyncio.sleep(30)
    while True:
        await fetch()
        await asyncio.sleep(24 * 3600)

# Хендлери
@dp.message(CommandStart())
async def start(m: types.Message):
    kb = [[types.InlineKeyboardButton(text="Отримати комбо", callback_data="combo")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка", callback_data="admin")])
    await m.answer("Привіт! Натисни кнопку:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "combo")
async def combo(c: types.CallbackQuery):
    uid = c.from_user.id
    if uid == ADMIN_ID or active or uid in subs:
        t = f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo_text}"
        await c.message.edit_text(t, parse_mode="HTML")
    else:
        await c.answer("Тільки для преміум", show_alert=True)

# Адмінські команди
@dp.message(Command("seturl"))
async def seturl(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        global source_url
        source_url = m.text.split(maxsplit=1)[1]
        save()
        await m.answer(f"URL збережено:\n{source_url}")
    except:
        await m.answer("Використання: /seturl https://...")

@dp.message(Command("setcombo"))
async def setcombo(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    global combo_text
    combo_text = m.text.partition(" ")[2] or "Комбо порожнє"
    save()
    await m.answer("Комбо оновлено вручну")

# Запуск
async def main():
    asyncio.create_task(scheduler())
    logging.info("БОТ ЗАПУЩЕНО — ДАНІ НА VOLUME")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
