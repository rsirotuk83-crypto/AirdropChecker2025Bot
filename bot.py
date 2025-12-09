import os
import asyncio
import json
import logging
import httpx
from datetime import datetime
from pathlib import Path
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.exceptions import TelegramBadRequest

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN or not WEBHOOK_HOST:
    raise RuntimeError("BOT_TOKEN або WEBHOOK_HOST не задані")

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

# -------------------------------------------------
# STORAGE
# -------------------------------------------------
class ComboStorage:
    DATA_DIR = Path("/app/data")
    DATA_FILE = DATA_DIR / "db.json"

    def __init__(self):
        self._combo = "Комбо ще не встановлено"
        self._url = ""
        self._lock = asyncio.Lock()
        self._load()

    def _load(self):
        if self.DATA_FILE.exists():
            try:
                with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._combo = data.get("combo", self._combo)
                    self._url = data.get("url", "")
                logger.info("Storage loaded")
            except Exception as e:
                logger.warning(f"Storage load error: {e}")

    async def _save(self):
        async with self._lock:
            self.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({"combo": self._combo, "url": self._url}, f)

    async def get_combo(self):
        async with self._lock:
            return self._combo

    async def set_combo(self, value: str):
        async with self._lock:
            self._combo = value
        await self._save()

    async def get_url(self):
        async with self._lock:
            return self._url

    async def set_url(self, url: str):
        async with self._lock:
            self._url = url
        await self._save()

storage = ComboStorage()

# -------------------------------------------------
# BOT
# -------------------------------------------------
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# -------------------------------------------------
# FETCH LOGIC
# -------------------------------------------------
async def fetch_combo():
    url = await storage.get_url()
    if not url:
        logger.warning("No source URL set")
        return

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            r.raise_for_status()

        text = r.text.strip()
        if not text:
            return

        old = await storage.get_combo()
        if text != old:
            await storage.set_combo(text)
            logger.info("Combo updated")

            if ADMIN_ID:
                await bot.send_message(ADMIN_ID, "✅ Комбо оновлено")

    except Exception as e:
        logger.error(f"Fetch error: {e}")

async def scheduler():
    await asyncio.sleep(30)
    while True:
        await fetch_combo()
        await asyncio.sleep(86400)

# -------------------------------------------------
# HANDLERS
# -------------------------------------------------
@dp.message(CommandStart())
async def start(m: types.Message):
    kb = [[types.InlineKeyboardButton(text="📦 Отримати комбо", callback_data="getcombo")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="⚙️ Адмінка", callback_data="admin")])

    await m.answer(
        "<b>👋 Вітаю!</b>\n\n"
        "Я CryptoComboDaily бот.\n"
        "Тут ти знайдеш актуальне комбо 👇",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(F.data == "getcombo")
async def getcombo(c: types.CallbackQuery):
    combo = await storage.get_combo()
    await c.message.edit_text(
        f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo}",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton("⬅ Назад", callback_data="back")]]
        )
    )
    await c.answer()

@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Немає доступу", show_alert=True)

    url = await storage.get_url()
    await c.message.edit_text(
        f"<b>Адмінка</b>\n\n"
        f"URL: <code>{url or 'не встановлено'}</code>",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton("🔄 Оновити зараз", callback_data="force")],
                [types.InlineKeyboardButton("⬅ Назад", callback_data="back")]
            ]
        )
    )
    await c.answer()

@dp.callback_query(F.data == "force")
async def force(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return
    await fetch_combo()
    await c.answer("Оновлено")

@dp.callback_query(F.data == "back")
async def back(c: types.CallbackQuery):
    await start(c.message)
    await c.answer()

@dp.message(Command("seturl"))
async def seturl(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    url = m.text.partition(" ")[2].strip()
    if not url.startswith("http"):
        return await m.answer("❌ Невірний URL")
    await storage.set_url(url)
    await m.answer("✅ URL збережено")
    await fetch_combo()

@dp.message(Command("setcombo"))
async def setcombo(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    combo = m.text.partition(" ")[2].strip()
    await storage.set_combo(combo)
    await m.answer("✅ Комбо збережено")

# -------------------------------------------------
# WEBHOOK
# -------------------------------------------------
async def on_startup(app):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(scheduler())
    me = await bot.get_me()
    logger.info(f"Bot started as @{me.username}")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

app = web.Application()
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
