import asyncio
import logging
import os

import aiohttp
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from bs4 import BeautifulSoup

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # https://xxxxx.up.railway.app
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ================== SOURCES ==================
SOURCES = {
    "hamster": ("Hamster Kombat", "https://hamster-combo.com"),
    "tapswap": ("TapSwap", "https://miningcombo.com/tapswap-2/"),
    "blum": ("Blum", "https://miningcombo.com/blum-2/"),
    "cattea": ("CatTea", "https://miningcombo.com/cattea/"),
}

# ================== HELPERS ==================
async def fetch_text(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=15) as r:
            html = await r.text()

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 3]

    # відсікання сміття
    cleaned = "\n".join(lines[:25])
    return cleaned or "Комбо не знайдено."

def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=key)]
            for key, (name, _) in SOURCES.items()
        ]
    )

# ================== HANDLERS ==================
@router.message(F.text == "/start")
async def start(msg: Message):
    await msg.answer(
        "🎮 *Обери гру для отримання щоденного комбо:*",
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

@router.callback_query(F.data.in_(SOURCES.keys()))
async def send_combo(cb: CallbackQuery):
    name, url = SOURCES[cb.data]

    await cb.answer("⏳ Шукаю комбо...")

    try:
        text = await fetch_text(url)
        await cb.message.edit_text(
            f"🎯 *{name} – щоденне комбо*\n\n{text}",
            reply_markup=main_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logging.exception(e)
        await cb.message.answer("❌ Помилка при отриманні комбо")

# ================== WEBHOOK ==================
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set: {WEBHOOK_URL}")

async def on_shutdown(app):
    await bot.delete_webhook()

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
