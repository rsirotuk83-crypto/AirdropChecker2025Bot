import os
import asyncio
import json
import logging
import httpx
from datetime import datetime
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_STATIC_URL')}{WEBHOOK_PATH}"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === Дані в Volume ===
DATA_FILE = "/app/data/db.json"
combo_text = "Комбо ще не встановлено"
source_url = ""

def load():
    global combo_text, source_url
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                combo_text = data.get("combo", combo_text)
                source_url = data.get("url", "")
        except: pass

def save():
    os.makedirs("/app/data", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"combo": combo_text, "url": source_url}, f, ensure_ascii=False)

load()

# === Оновлення ===
async def fetch():
    global combo_text
    if not source_url: return
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(source_url)
            if r.status_code == 200:
                new = r.text.strip()
                if new and new != combo_text:
                    combo_text = new
                    save()
                    if ADMIN_ID:
                        await bot.send_message(ADMIN_ID, "Комбо оновлено!")
    except Exception as e:
        logging.error(f"Помилка fetch: {e}")

async def scheduler():
    await asyncio.sleep(30)
    while True:
        await fetch()
        await asyncio.sleep(24 * 3600)

# === Хендлери ===
@dp.message(CommandStart())
async def start(m: types.Message):
    kb = [[types.InlineKeyboardButton(text="Отримати комбо", callback_data="combo")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка", callback_data="admin")])
    await m.answer("Привіт! @CryptoComboDaily\nНатисни кнопку:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "combo")
async def show_combo(c: types.CallbackQuery):
    await c.message.edit_text(f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo_text}", parse_mode="HTML")

@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    await c.message.edit_text("Адмінка", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Оновити зараз", callback_data="force")]
    ]))

@dp.callback_query(F.data == "force")
async def force(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    await fetch()
    await c.answer("Оновлено!")

@dp.message(F.text.startswith("/seturl"))
async def seturl(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        global source_url
        source_url = m.text.split(maxsplit=1)[1]
        save()
        await m.answer(f"URL збережено:\n{source_url}")
        await fetch()
    except:
        await m.answer("Використання: /seturl https://...")

@dp.message(F.text.startswith("/setcombo"))
async def setcombo(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    global combo_text
    combo_text = m.text.partition(" ")[2] or "Порожнє"
    save()
    await m.answer("Комбо збережено")

# === Webhook ===
async def on_startup(app):
    await bot.set_webhook(f"{WEBHOOK_URL}")
    asyncio.create_task(scheduler())
    logging.info(f"Webhook встановлено: {WEBHOOK_URL}")

app = web.Application()
app.on_startup.append(on_startup)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
