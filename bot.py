import os
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

from parsers import (
    get_hamster_combo,
    get_miningcombo
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # https://xxx.up.railway.app
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN or not WEBHOOK_HOST:
    raise RuntimeError("BOT_TOKEN або WEBHOOK_HOST не встановлено")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== BOT ==================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ================== STORAGE ==================
DATA_PATH = Path("/app/data")
DATA_FILE = DATA_PATH / "combos.json"


class ComboStorage:
    def __init__(self):
        self.data = {}
        self.lock = asyncio.Lock()
        self.load()

    def load(self):
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    async def save(self):
        async with self.lock:
            DATA_PATH.mkdir(parents=True, exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)

    async def set(self, game: str, combo: str, source: str):
        async with self.lock:
            self.data[game] = {
                "combo": combo,
                "source": source,
                "updated": datetime.utcnow().isoformat()
            }
        await self.save()

    async def get(self, game: str):
        async with self.lock:
            return self.data.get(game)


storage = ComboStorage()

# ================== UPDATE LOGIC ==================
async def update_all_combos(force=False):
    logger.info("Оновлення комбо...")

    sources = [
        ("hamster", get_hamster_combo),
        ("tapswap", lambda: get_miningcombo("tapswap")),
        ("blum", lambda: get_miningcombo("blum")),
        ("cattea", lambda: get_miningcombo("cattea")),
    ]

    for game, func in sources:
        try:
            result = func()
            if "combo" in result:
                await storage.set(
                    game,
                    result["combo"],
                    result["source"]
                )
                logger.info(f"{game} ✅ оновлено")
        except Exception as e:
            logger.warning(f"{game} ❌ {e}")

    if force and ADMIN_ID:
        await bot.send_message(ADMIN_ID, "✅ Комбо оновлено вручну")


async def scheduler():
    await asyncio.sleep(20)
    while True:
        await update_all_combos()
        await asyncio.sleep(60 * 60 * 24)  # 1 раз на добу


# ================== UI ==================
def main_keyboard(is_admin=False):
    kb = [
        [types.InlineKeyboardButton(text="🐹 Hamster", callback_data="combo_hamster")],
        [types.InlineKeyboardButton(text="🟡 TapSwap", callback_data="combo_tapswap")],
        [types.InlineKeyboardButton(text="🟢 Blum", callback_data="combo_blum")],
        [types.InlineKeyboardButton(text="🟣 Cattea", callback_data="combo_cattea")]
    ]
    if is_admin:
        kb.append([types.InlineKeyboardButton(text="🔄 Оновити зараз", callback_data="force_update")])
    return types.InlineKeyboardMarkup(inline_keyboard=kb)


# ================== HANDLERS ==================
@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer(
        "🚀 <b>Crypto Combo Daily</b>\n\n"
        "Обери гру та отримай актуальне комбо 👇",
        reply_markup=main_keyboard(m.from_user.id == ADMIN_ID)
    )


@dp.callback_query(F.data.startswith("combo_"))
async def show_combo(c: types.CallbackQuery):
    game = c.data.replace("combo_", "")
    data = await storage.get(game)

    if not data:
        await c.answer("❌ Комбо ще не оновлено", show_alert=True)
        return

    await c.message.edit_text(
        f"🎮 <b>{game.upper()}</b>\n\n"
        f"🎯 <b>{data['combo']}</b>\n\n"
        f"🗓 Оновлено: {data['updated'][:10]}\n"
        f"🔗 <a href='{data['source']}'>Джерело</a>",
        reply_markup=main_keyboard(c.from_user.id == ADMIN_ID)
    )


@dp.callback_query(F.data == "force_update")
async def force(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return
    await update_all_combos(force=True)
    await c.answer("✅ Оновлено!")


# ================== WEBHOOK ==================
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
