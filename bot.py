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
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

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
}

# ================== ПАРСЕРИ (оновлено для CatTea) ==================
def parse_hamster(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    header = soup.find(lambda tag: tag.name in ["h1", "h2", "h3", "h4"] and "combo" in tag.get_text(strip=True).lower())
    if not header:
        return "⏳ <b>Комбо ще не опубліковане</b>"
    cards = []
    for tag in header.find_all_next(["p", "li", "div", "span", "strong"]):
        text = tag.get_text(strip=True)
        if text.isupper() and 4 <= len(text) <= 30 and text not in cards:
            cards.append(text)
        if len(cards) >= 3:
            break
    if len(cards) < 3:
        return "⏳ <b>Комбо ще не опубліковане</b>"
    return "\n".join(f"• <b>{c}</b>" for c in cards[:3])

def parse_tapswap(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    codes = []
    for tag in soup.find_all(["p", "div", "span", "strong"]):
        text = tag.get_text(strip=True)
        if "code" in text.lower() or "cipher" in text.lower():
            parts = text.split()
            for part in parts[::-1]:
                if part.isalnum() and len(part) >= 4:
                    codes.append(part.upper())
                    break
    codes = list(dict.fromkeys(codes))  # дублі
    return "\n".join(f"• <b>{c}</b>" for c in codes[:5]) or "⏳ <b>Комбо ще не знайдено</b>"

def parse_blum(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    codes = []
    for tag in soup.find_all(["strong", "p", "span", "div"]):
        text = tag.get_text(strip=True)
        if text.isupper() and 5 <= len(text) <= 20 and text not in codes:
            codes.append(text)
        if len(codes) >= 3:
            break
    return "\n".join(f"• <b>{c}</b>" for c in codes[:3]) or "⏳ <b>Комбо ще не знайдено</b>"

def parse_cattea(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if "searching" in html.lower() or "coming soon" in html.lower() or "we are searching" in html.lower():
        return "⏳ <b>Комбо ще не знайдено (searching...)</b>"
    header = soup.find(lambda tag: tag.name in ["h2", "h3", "h4"] and "cattea" in tag.get_text(strip=True).lower())
    if not header:
        return "⏳ <b>Комбо ще не опубліковане</b>"
    cards = []
    for tag in header.find_all_next(["p", "li", "div", "strong", "span"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 3 and text not in cards:
            cards.append(text)
        if len(cards) >= 4:
            break
    if len(cards) < 3:
        return "⏳ <b>Комбо ще не знайдено</b>"
    return "\n".join(f"• <b>{c}</b>" for c in cards[:4])

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
        "cattea": "🐱 CatTea"
    }[game]
    try:
        html = await fetch(SOURCES[game])
        if game == "hamster":
            combo = parse_hamster(html)
        elif game == "tapswap":
            combo = parse_tapswap(html)
        elif game == "blum":
            combo = parse_blum(html)
        else:
            combo = parse_cattea(html)
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
