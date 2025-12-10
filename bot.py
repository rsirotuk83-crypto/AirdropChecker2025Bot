import os
import asyncio
import logging
import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# ================== CONFIG & LOGGING ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", 8080))

if not BOT_TOKEN or not WEBHOOK_HOST:
    raise RuntimeError("BOT_TOKEN або WEBHOOK_HOST не встановлено")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"  # ВИПРАВЛЕНО!

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ================== SOURCES ==================
SOURCES = {
    "hamster": "https://hamster-combo.com",
    "tapswap": "https://miningcombo.com/tapswap-2/",
    "blum": "https://miningcombo.com/blum-2/",
    "cattea": "https://miningcombo.com/cattea/",
    "tonstation": "https://miningcombo.com/ton-station/",
}

# ================== ПАРСЕРИ ==================
# (твій останній робочий варіант парсерів — без змін)

# ================== FETCH ==================
async def fetch(url: str) -> str:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(url, follow_redirects=True)
        r.raise_for_status()
        return r.text

# ================== UI ==================
def main_kb():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="🐹 Hamster", callback_data="hamster"),
            types.InlineKeyboardButton(text="⚡ TapSwap", callback_data="tapswap")
        ],
        [
            types.InlineKeyboardButton(text="🌸 Blum", callback_data="blum"),
            types.InlineKeyboardButton(text="🐱 CatTea", callback_data="cattea")
        ],
        [
            types.InlineKeyboardButton(text="🚉 TON Station", callback_data="tonstation")
        ]
    ])

def back_kb():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="<< Назад до меню", callback_data="back_to_menu")]
    ])

# ================== HANDLERS ==================
@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer("<b>🎮 Щоденні комбо ігор</b>\n\nОбери гру:", reply_markup=main_kb())

@dp.callback_query(F.data.in_(SOURCES.keys()))
async def send_combo(cb: types.CallbackQuery):
    await cb.answer("Отримую дані...", cache_time=5)
    game = cb.data
    name = {
        "hamster": "🐹 Hamster Kombat",
        "tapswap": "⚡ TapSwap",
        "blum": "🌸 Blum",
        "cattea": "🐱 CatTea",
        "tonstation": "🚉 TON Station"
    }[game]
    try:
        html = await fetch(SOURCES[game])
        if game == "hamster":
            combo = parse_hamster(html)
        elif game == "tapswap":
            combo = parse_tapswap(html)
        elif game == "blum":
            combo = parse_blum(html)
        elif game == "cattea":
            combo = parse_cattea(html)
        else:
            combo = parse_tonstation(html)
        text = f"<b>{name}</b>\nКомбо на <b>{datetime.now():%d.%m.%Y}</b>\n\n{combo}"
    except Exception as e:
        log.error(f"Error for {game}: {e}")
        text = f"❌ <b>Помилка для {name}</b>\nСпробуйте пізніше."
    try:
        await cb.message.edit_text(text, reply_markup=back_kb())
    except:
        await cb.message.answer(text, reply_markup=back_kb())

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(cb: types.CallbackQuery):
    await cb.answer()
    await cb.message.edit_text("<b>🎮 Щоденні комбо ігор</b>\n\nОбери гру:", reply_markup=main_kb())

# ================== WEBHOOK ==================
async def on_startup(app: web.Application):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    log.info(f"Webhook встановлено: {WEBHOOK_URL}")

app = web.Application()
app.on_startup.append(on_startup)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

if __name__ == "__main__":
    log.info(f"Запуск сервера на 0.0.0.0:{PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)
