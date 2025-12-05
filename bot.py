import os
import asyncio
import json
import logging
import httpx
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

# === Логування ===
logging.basicConfig(level=logging.INFO)

# === Токен і адмін ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not ADMIN_ID:
    logging.error("Помилка: не встановлено BOT_TOKEN або ADMIN_ID")
    exit(1)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# === Volume (Railway) ===
DATA_DIR = "/app/data"
DB_PATH = os.path.join(DATA_DIR, "db.json")
os.makedirs(DATA_DIR, exist_ok=True)

# === Стан ===
subs = {}           # преміум-користувачі
active = False      # глобальний доступ
combo_text = "Комбо ще не встановлено"
source_url = ""     # твій .txt URL

# === Завантаження / збереження ===
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
            logging.info("Дані завантажено з Volume")
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

# Адмін завжди має преміум
if ADMIN_ID and ADMIN_ID not in subs:
    subs[ADMIN_ID] = True
    save()

# === Автооновлення ===
async def fetch():
    global combo_text
    if not source_url:
        return
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(source_url)
            if r.status_code == 200:
                new = r.text.strip()
                if new and new != combo_text:
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

# === Хендлери ===
@dp.message(CommandStart())
async def start(m: types.Message):
    uid = m.from_user.id
    kb = [[types.InlineKeyboardButton(text="Отримати комбо", callback_data="combo")]]
    if uid == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка", callback_data="admin")])
    await m.answer("Привіт! @CryptoComboDaily\nНатисни кнопку:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "combo")
async def show_combo(c: types.CallbackQuery):
    uid = c.from_user.id
    if uid == ADMIN_ID or active or uid in subs:
        t = f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo_text}"
        await c.message.edit_text(t, parse_mode="HTML")
    else:
        await c.answer("Тільки для преміум", show_alert=True)

@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return
    kb = [
        [types.InlineKeyboardButton(text="Оновити зараз", callback_data="force")],
        [types.InlineKeyboardButton(text="Увімкнути для всіх", callback_data="on")],
        [types.InlineKeyboardButton(text="Вимкнути", callback_data="off")]
    ]
    await c.message.edit_text("Адмінка", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.in_({"force", "on", "off"}))
async def admin_actions(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return
    if c.data == "force":
        await fetch()
        await c.answer("Оновлено!")
    elif c.data == "on":
        global active
        active = True
        save()
        await c.answer("Увімкнено для всіх")
    elif c.data == "off":
        global active
        active = False
        save()
        await c.answer("Вимкнено")

# === Адмін-команди ===
@dp.message(F.text.startswith("/seturl"))
async def seturl(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    try:
        global source_url
        source_url = m.text.split(maxsplit=1)[1]
        save()
        await m.answer(f"URL збережено:\n{source_url}")
    except:
        await m.answer("Використання: /seturl https://...")

@dp.message(F.text.startswith("/setcombo"))
async def setcombo(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    global combo_text
    combo_text = m.text.partition(" ")[2] or "Порожнє"
    save()
    await m.answer("Комбо збережено")

# === Запуск ===
async def main():
    asyncio.create_task(scheduler())
    logging.info("БОТ УСПІШНО ЗАПУЩЕНО — ГОТОВИЙ ДО РОБОТИ")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
