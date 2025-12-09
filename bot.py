import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from aiohttp import web


# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)


# =========================
# ENV
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", "8080"))


if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN not set")
if not WEBHOOK_HOST:
    raise RuntimeError("❌ WEBHOOK_HOST not set")


WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"


# =========================
# BOT / DP
# =========================
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()


# =========================
# HANDLERS
# =========================
@router.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 <b>Вітаю!</b>\n\n"
        "🎮 Тут ти отримуєш актуальні комбо для TON-ігор\n"
        "✅ швидко\n"
        "✅ без пошуку по чатах\n\n"
        "👉 Сьогоднішнє комбо доступне преміум-підписникам"
    )


dp.include_router(router)


# =========================
# STARTUP / SHUTDOWN
# =========================
async def on_startup(bot: Bot):
    # 🔍 самоперевірка токена
    me = await bot.get_me()
    log.info(f"✅ Bot authorized as @{me.username}")

    await bot.set_webhook(
        WEBHOOK_URL,
        drop_pending_updates=True
    )
    log.info(f"✅ Webhook set: {WEBHOOK_URL}")


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    await bot.session.close()
    log.info("🛑 Bot shutdown")


dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)


# =========================
# WEB APP
# =========================
def main():
    app = web.Application()

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    ).register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    log.info(f"🚀 Starting webhook server on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
