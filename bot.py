import logging
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не встановлено")

if not WEBHOOK_URL:
    raise RuntimeError("❌ WEBHOOK_URL не встановлено")

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_FULL_URL = WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# =======================
# /start
# =======================
@router.message(CommandStart())
async def cmd_start(message: Message):
    logger.info(f"/start від user={message.from_user.id}")

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Back to start", callback_data="back_to_start")

    await message.answer(
        "✅ Бот працює стабільно.\nНатисни кнопку ⬇️",
        reply_markup=kb.as_markup()
    )


# =======================
# CALLBACK
# =======================
@router.callback_query(lambda c: c.data == "back_to_start")
async def back_to_start(cb: CallbackQuery):
    logger.info(f"back_to_start від user={cb.from_user.id}")

    await cb.message.edit_text(
        "🔁 Повернення на старт ✅",
        reply_markup=cb.message.reply_markup
    )
    await cb.answer()


# =======================
# FALLBACK
# =======================
@router.message()
async def fallback(message: Message):
    await message.answer("Я на звʼязку ✅\nНатисни /start")


# =======================
# WEBHOOK
# =======================
async def on_startup(app):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_FULL_URL)
    logger.info(f"✅ Webhook встановлено: {WEBHOOK_FULL_URL}")


async def handle_webhook(request):
    data = await request.json()
    await dp.feed_raw_update(bot, data)
    return web.Response(text="ok")


def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.on_startup.append(on_startup)

    logger.info("🚀 Запуск сервера")
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
