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
WEBHOOK_URL = f"{WEBHOOK_HOST  HOST}{WEBHOOK_PATH}"

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

# ================== ПАРСЕРИ (оновлено для картинок) ==================
async def fetch(url: str) -> str:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(url, follow_redirects=True)
        r.raise_for_status()
        return r.text

def parse_images(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    images = []
    for img in soup.find_all("img"):
        src = img.get("src")
        alt = img.get("alt", "")
        if src:
            if not src.startswith("http"):
                src = "https://miningcombo.com" + src if "miningcombo" in SOURCES.values()[0] else src
            if "combo" in alt.lower() or "card" in alt.lower() or "daily" in alt.lower():
                images.append(src)
    return images[:4]  # зазвичай 3-4 картки

async def get_combo_with_images(game: str) -> tuple[str, list]:
    html = await fetch(SOURCES[game])
    images = parse_images(html)
    if images:
        return "Комбо у вигляді картинок:", images
    # fallback на текстовий парсер (як раніше)
    # ... (твій старий текстовий парсер тут)
    return "Текст комбо (як раніше)", []

# ================== HANDLERS ==================
@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer("<b>🎮 Щоденні комбо ігор</b>\n\nОбери гру:", reply_markup=main_kb())

@dp.callback_query(F.data.in_(SOURCES.keys()))
async def send_combo(cb: types.CallbackQuery):
    await cb.answer("Отримую дані...", cache_time=5)
    game = cb.data
    name = { ... }[game]
    text, images = await get_combo_with_images(game)
    caption = f"<b>{name}</b>\nКомбо на <b>{datetime.now():%d.%m.%Y}</b>\n\n{text}"
    if images:
        media = types.MediaGroup()
        for img in images:
            media.attach_photo(types.InputMediaPhoto(img))
        await cb.message.answer_media_group(media)
        await cb.message.answer(caption + "\nКартинки комбо вище ↑", reply_markup=back_kb())
    else:
        await cb.message.edit_text(caption, reply_markup=back_kb())

# ... решта коду без змін

# ================== WEBHOOK ==================
# (без змін)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
