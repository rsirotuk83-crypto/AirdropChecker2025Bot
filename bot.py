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

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", 8080))

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()

# ================== SOURCES ==================
SOURCES = {
    "hamster": "https://hamster-combo.com",
    "tapswap": "https://miningcombo.com/tapswap-2/",
    "blum": "https://miningcombo.com/blum-2/",
    "cattea": "https://miningcombo.com/cattea/",
}

# ================== PARSERS ==================
def parse_hamster(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    cards = []
    for tag in soup.find_all(["h3", "strong"]):
        text = tag.get_text(strip=True)
        if text.isupper() and 4 < len(text) < 25:
            cards.append(text)

    if not cards:
        return "⏳ *Комбо ще не опубліковане*"

    return "\n".join(f"• {c}" for c in cards[:3])


def parse_codes_by_label(html: str, label="Code") -> str:
    soup = BeautifulSoup(html, "html.parser")
    lines = soup.get_text("\n").splitlines()

    codes = []
    for i, line in enumerate(lines):
        if label in line and i + 1 < len(lines):
            code = lines[i + 1].strip()
            if 2 <= len(code) <= 15 and code.isalnum():
                codes.append(code)

    return "\n".join(f"• {c}" for c in codes[:5]) or "⏳ *Комбо ще не знайдено*"


def parse_cattea(html: str) -> str:
    if "searching for today's" in html.lower():
        return "⏳ *CatTea ще не оновив комбо*"

    soup = BeautifulSoup(html, "html.parser")
    codes = []

    for li in soup.find_all("li"):
        text = li.get_text(strip=True)
        if 3 <= len(text) <= 20 and text.isalnum():
            codes.append(text)

    return "\n".join(f"• {c}" for c in codes[:5]) or "⏳ *Комбо не знайдено*"


# ================== FETCH ==================
async def fetch(url: str) -> str:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(url, follow_redirects=True)
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
        ]
    ])


# ================== HANDLERS ==================
@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer(
        "🎮 *Щоденні комбо ігор*\n\nОбери гру:",
        reply_markup=main_kb()
    )


@dp.callback_query(F.data.in_(SOURCES.keys()))
async def send_combo(cb: types.CallbackQuery):
    await cb.answer()

    game = cb.data
    html = await fetch(SOURCES[game])

    if game == "hamster":
        combo = parse_hamster(html)
        name = "🐹 Hamster Kombat"
    elif game == "tapswap":
        combo = parse_codes_by_label(html)
        name = "⚡ TapSwap"
    elif game == "blum":
        combo = parse_codes_by_label(html)
        name = "🌸 Blum"
    else:
        combo = parse_cattea(html)
        name = "🐱 CatTea"

    text = (
        f"{name}\n"
        f"*Комбо на {datetime.now():%d.%m.%Y}*\n\n"
        f"{combo}"
    )

    await cb.message.edit_text(text, reply_markup=main_kb())


# ================== WEBHOOK ==================
async def on_startup(app):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    log.info(f"Webhook set: {WEBHOOK_URL}")

app = web.Application()
app.on_startup.append(on_startup)

SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
