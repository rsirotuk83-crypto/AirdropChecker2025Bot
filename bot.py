import os
import asyncio
import json
import logging
import requests
from datetime import datetime
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN or not WEBHOOK_HOST:
    raise RuntimeError("BOT_TOKEN або WEBHOOK_HOST не встановлено")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= BOT =================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ================= STORAGE =================
DATA_PATH = Path("/app/data")
DATA_FILE = DATA_PATH / "combos.json"


class Storage:
    def __init__(self):
        self.data = {}
        self.lock = asyncio.Lock()
        self.load()

    def load(self):
        if DATA_FILE.exists():
            try:
                self.data = json.loads(DATA_FILE.read_text())
            except:
                self.data = {}

    async def save(self):
        async with self.lock:
            DATA_PATH.mkdir(parents=True, exist_ok=True)
            DATA_FILE.write_text(json.dumps(self.data, ensure_ascii=False, indent=2))

    async def set(self, game, combo, source):
        async with self.lock:
            self.data[game] = {
                "combo": combo,
                "source": source,
                "updated": datetime.now().strftime("%d.%m.%Y")
            }
        await self.save()

    async def get(self, game):
        async with self.lock:
            return self.data.get(game)


storage = Storage()

# ================= FETCH =================
def fetch_text(url):
    r = requests.get(url, timeout=15)
    if r.status_code != 200:
        raise Exception("Fetch failed")
    return r.text.strip()


async def update_combos():
    sources = {
        "hamster": "https://hamster-combo.com",
        "tapswap": "https://miningcombo.com/tapswap-2/",
        "blum": "https://miningcombo.com/blum-2/",
        "cattea": "https://miningcombo.com/cattea/"
    }

    for game, url in sources.items():
        try:
            text = fetch_text(url)
            await storage.set(game, text[:1500], url)
            logger.info(f"{game} updated")
        except Exception as e:
            logger.warning(f"{game} error: {e}")


async def scheduler():
    await asyncio.sleep(20)
    while True:
        await update_combos()
        if ADMIN_ID:
            await bot.send_message(ADMIN_ID, "✅ Комбо оновлено")
        await asyncio.sleep(86400)

# ================= UI =================
def keyboard(admin=False):
    kb = [
        [types.InlineKeyboardButton(text="🐹 Hamster", callback_data="combo_hamster")],
        [types.InlineKeyboardButton(text="🟡 TapSwap", callback_data="combo_tapswap")],
        [types.InlineKeyboardButton(text="🟢 Blum", callback_data="combo_blum")],
        [types.InlineKeyboardButton(text="🟣 Cattea", callback_data="combo_cattea")],
    ]
    if admin:
        kb.append([types.InlineKeyboardButton(text="🔄 Оновити", callback_data="force")])
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

# ================= HANDLERS =================
@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer(
        "🚀 <b>Crypto Combo Daily</b>\nОбери гру:",
        reply_markup=keyboard(m.from_user.id == ADMIN_ID)
    )


@dp.callback_query(F.data.startswith("combo_"))
async def send_combo(c: types.CallbackQuery):
    game = c.data.replace("combo_", "")
    data = await storage.get(game)

    if not data:
        await c.answer("❌ Комбо ще не готове", show_alert=True)
        return

    await c.message.edit_text(
        f"<b>{game.upper()}</b>\n\n"
        f"{data['combo']}\n\n"
        f"🗓 {data['updated']}\n"
        f"🔗 <a href='{data['source']}'>Джерело</a>",
        reply_markup=keyboard(c.from_user.id == ADMIN_ID)
    )


@dp.callback_query(F.data == "force")
async def force_update(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return
    await update_combos()
    await c.answer("✅ Оновлено")

# ================= WEBHOOK =================
async def on_startup(app):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(scheduler())
    logger.info(f"Webhook set: {WEBHOOK_URL}")


app = web.Application()
app.on_startup.append(on_startup)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
