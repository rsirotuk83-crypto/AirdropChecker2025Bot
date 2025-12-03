import os
import asyncio
import json
import logging
import httpx
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ===================== НАЛАШТУВАННЯ =====================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not CRYPTO_BOT_TOKEN or not ADMIN_ID:
    logging.error("Помилка: не встановлено BOT_TOKEN / CRYPTO_BOT_TOKEN / ADMIN_ID")
    exit(1)

# ===================== СТАН =====================
DB_FILE = "db_state.json"
USER_SUBSCRIPTIONS: dict[int, bool] = {}
IS_ACTIVE = False
COMBO_CONTENT = "Комбо ще не встановлено адміністратором."
AUTO_SOURCE_URL = ""        # ← сюди ставиш прямий .txt URL (наприклад https://miningcombo.com/raw.txt)

# ===================== ПЕРСИСТЕНТНІСТЬ =====================
def load_state():
    global USER_SUBSCRIPTIONS, IS_ACTIVE, COMBO_CONTENT, AUTO_SOURCE_URL
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                USER_SUBSCRIPTIONS = {int(k): v for k, v in data.get("subs", {}).items()}
                IS_ACTIVE = data.get("active", False)
                COMBO_CONTENT = data.get("combo", COMBO_CONTENT)
                AUTO_SOURCE_URL = data.get("url", "")
            logging.info("Стан завантажено")
        except Exception as e:
            logging.error(f"Помилка завантаження стану: {e}")

def save_state():
    data = {
        "subs": USER_SUBSCRIPTIONS,
        "active": IS_ACTIVE,
        "combo": COMBO_CONTENT,
        "url": AUTO_SOURCE_URL
    }
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Помилка збереження: {e}")

load_state()

# ===================== БОТ =====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()

# ===================== АВТООНОВЛЕННЯ =====================
async def fetch_combo():
    global COMBO_CONTENT
    if not AUTO_SOURCE_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(AUTO_SOURCE_URL)
            r.raise_for_status()
            new = r.text.strip()
            if new and new != COMBO_CONTENT:
                COMBO_CONTENT = new
                save_state()
                logging.info("Комбо автоматично оновлено")
                await bot.send_message(ADMIN_ID, "Комбо оновлено автоматично!")
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"Помилка автооновлення:\n{e}")

async def scheduler():
    await asyncio.sleep(20)
    while True:
        await fetch_combo()
        await asyncio.sleep(24 * 60 * 60)   # кожні 24 години

# ===================== ХЕНДЛЕРИ =====================
@dp.message(CommandStart())
async def start(msg: types.Message):
    uid = msg.from_user.id
    name = msg.from_user.first_name or "друже"
    premium = USER_SUBSCRIPTIONS.get(uid, False)

    text = f"Привіт, **{name}**!\n\n"
    if uid == ADMIN_ID:
        text += f"Автооновлення: {'вкл' if AUTO_SOURCE_URL else 'викл'}\n"

    kb = [[types.InlineKeyboardButton(text="Отримати комбо", callback_data="combo")]]
    if uid == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка", callback_data="admin")])
    elif not premium:
        kb.insert(0, [types.InlineKeyboardButton(text="Купити преміум 1 TON", callback_data="buy")])

    await msg.answer(text + "Обери дію:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "combo")
async def send_combo(cb: types.CallbackQuery):
    uid = cb.from_user.id
    if uid == ADMIN_ID or IS_ACTIVE or USER_SUBSCRIPTIONS.get(uid, False):
        date = datetime.now().strftime("%d.%m.%Y")
        text = f"**Комбо та коди на {date}**\n\n{COMBO_CONTENT}"
        await cb.message.edit_text(text, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await cb.answer("Тільки для преміум-користувачів", show_alert=True)

@dp.callback_query(F.data == "buy")
async def buy(cb
