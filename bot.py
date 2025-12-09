import os
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

import httpx
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.exceptions import TelegramBadRequest

# -------------------- CONFIG --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN or not WEBHOOK_HOST:
    raise RuntimeError("BOT_TOKEN або WEBHOOK_HOST не встановлено")

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# -------------------- STORAGE --------------------
class Storage:
    path = Path("/app/data")
    file = path / "db.json"

    def __init__(self):
        self.lock = asyncio.Lock()
        self.combo = "Комбо ще не встановлено"
        self.url = ""
        self._load()

    def _load(self):
        if self.file.exists():
            try:
                with open(self.file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.combo = data.get("combo", self.combo)
                    self.url = data.get("url", "")
                    logger.info("DB loaded")
            except Exception as e:
                logger.error(f"DB load error: {e}")

    async def save(self):
        async with self.lock:
            self.path.mkdir(parents=True, exist_ok=True)
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump({"combo": self.combo, "url": self.url}, f)

storage = Storage()

# -------------------- BOT --------------------
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# -------------------- UI --------------------
def main_keyboard(user_id: int):
    kb = [
        [types.InlineKeyboardButton(text="📦 Отримати комбо", callback_data="getcombo")]
    ]
    if user_id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="⚙️ Адмінка", callback_data="admin")])
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

async def show_main_menu(message: types.Message):
    await message.answer(
        "👋 <b>CryptoComboDaily</b>\n\n"
        "Отримуйте актуальні комбо для TON-ігор.",
        reply_markup=main_keyboard(message.from_user.id)
    )

async def edit_main_menu(message: types.Message, user_id: int):
    await message.edit_text(
        "👋 <b>CryptoComboDaily</b>\n\n"
        "Отримуйте актуальні комбо для TON-ігор.",
        reply_markup=main_keyboard(user_id)
    )

# -------------------- HANDLERS --------------------
@dp.message(CommandStart())
async def start(message: types.Message):
    logger.info(f"/start від {message.from_user.id}")
    await show_main_menu(message)

@dp.callback_query(F.data == "getcombo")
async def get_combo(cb: types.CallbackQuery):
    await cb.message.edit_text(
        f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{storage.combo}",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton("⬅ Назад", callback_data="back")]]
        )
    )
    await cb.answer()

@dp.callback_query(F.data == "back")
async def back(cb: types.CallbackQuery):
    await edit_main_menu(cb.message, cb.from_user.id)
    await cb.answer()

@dp.callback_query(F.data == "admin")
async def admin(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("⛔ Немає доступу", show_alert=True)
        return

    await cb.message.edit_text(
        f"<b>Адмінка</b>\n\nURL: <code>{storage.url or 'не встановлено'}</code>",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton("🔄 Оновити", callback_data="force")],
                [types.InlineKeyboardButton("⬅ Назад", callback_data="back")]
            ]
        )
    )
    await cb.answer()

@dp.callback_query(F.data == "force")
async def force(cb: types.CallbackQuery):
    if cb.from_user.id == ADMIN_ID:
        await fetch_combo()
        await cb.answer("✅ Готово")

@dp.message(Command("seturl"))
async def set_url(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Використання: /seturl https://example.com")
        return
    storage.url = parts[1]
    await storage.save()
    await message.answer("✅ URL збережено")

# -------------------- FALLBACK --------------------
@dp.message()
async def fallback(message: types.Message):
    await show_main_menu(message)

# -------------------- SCRAPER --------------------
async def fetch_combo():
    if not storage.url:
        logger.warning("URL не встановлено")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(storage.url)
            r.raise_for_status()
            if r.text.strip():
                storage.combo = r.text.strip()
                await storage.save()
    except Exception as e:
        logger.error(f"Scrape error: {e}")

# -------------------- WEBHOOK --------------------
async def on_startup(app):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook set")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

app = web.Application()
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

if __name__ == "__main__":
    logger.info("Starting server")
    web.run_app(app, host="0.0.0.0", port=PORT)
