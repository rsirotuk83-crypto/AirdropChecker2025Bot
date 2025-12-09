import os
import asyncio
import json
import logging
import httpx
from datetime import datetime
from aiohttp import web
from pathlib import Path
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.exceptions import TelegramBadRequest

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN or not WEBHOOK_HOST:
    logger.error("КРИТИЧНА ПОМИЛКА: BOT_TOKEN або WEBHOOK_HOST не встановлено.")
    raise RuntimeError("Перевір змінні")

# ВИПРАВЛЕНО: Безпечний шлях без двокрапки
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === Сховище ===
class ComboStorage:
    DATA_PATH = Path("/app/data")
    DATA_FILE = DATA_PATH / "db.json"
    def __init__(self):
        self._combo_text = "Комбо ще не встановлено"
        self._source_url = ""
        self._lock = asyncio.Lock()
        self.load()
    def load(self):
        if self.DATA_FILE.exists():
            try:
                with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    self._combo_text = d.get("combo", self._combo_text)
                    self._source_url = d.get("url", "")
            except: pass
    async def save(self):
        async with self._lock:
            self.DATA_PATH.mkdir(parents=True, exist_ok=True)
            try:
                with open(self.DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump({"combo": self._combo_text, "url": self._source_url}, f)
            except: pass
    async def get_combo(self):
        async with self._lock:
            return self._combo_text
    async def set_combo(self, text: str):
        async with self._lock:
            self._combo_text = text
        await self.save()
    async def get_url(self):
        async with self._lock:
            return self._source_url
    async def set_url(self, url: str):
        async with self._lock:
            self._source_url = url
        await self.save()

storage = ComboStorage()

# === Оновлення ===
async def fetch():
    source_url = await storage.get_url()
    if not source_url: return
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(source_url)
            if r.status_code == 200:
                new = r.text.strip()
                current = await storage.get_combo()
                if new and new != current:
                    await storage.set_combo(new)
                    if ADMIN_ID:
                        await bot.send_message(ADMIN_ID, "Комбо оновлено!")
    except: pass

async def scheduler():
    await asyncio.sleep(30)
    while True:
        await fetch()
        await asyncio.sleep(86400)

# === Хендлери ===
@dp.message(CommandStart())
async def start(m: types.Message):
    kb = [[types.InlineKeyboardButton(text="Отримати комбо", callback_data="getcombo")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка", callback_data="admin")])
    await m.answer("Привіт! @CryptoComboDaily\nНатисни кнопку:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "getcombo")
async def show_combo(c: types.CallbackQuery):
    combo = await storage.get_combo()
    await c.message.edit_text(f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo}", parse_mode="HTML")

@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    url = await storage.get_url()
    await c.message.edit_text(f"Адмінка\nURL: {url or 'не встановлено'}", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
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
        url = m.text.split(maxsplit=1)[1]
        await storage.set_url(url)
        await m.answer(f"URL збережено:\n{url}")
        await fetch()
    except:
        await m.answer("Використання: /seturl https://...")

# === Webhook ===
async def on_startup(app):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(scheduler())
    logging.info(f"Webhook встановлено: {WEBHOOK_URL}")

app = web.Application()
app.on_startup.append(on_startup)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
