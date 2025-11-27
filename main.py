from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Оплатить $1 → TON/USDT", url="https://t.me/CryptoBot?start=IVeOWQMbUYjt")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Самый быстрый аирдроп-чекер 2025–2026\n\n"
        "За 10 сек посчитаю всё по 15+ топ-проектам\n\n"
        "Цена: $1 навсегда\n\nЖми кнопку ↓",
        reply_markup=reply_markup
    )

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
