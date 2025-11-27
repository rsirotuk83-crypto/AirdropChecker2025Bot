import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [[InlineKeyboardButton("Оплатить $1 → TON/USDT",
                                     url=f"https://t.me/CryptoBot?start=IVeOWQMbUYjt_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Найшвидший аирдроп-чекер 2025–2026\n\n"
        "За 10 сек порахую все по 15+ топ-проектам\n\n"
        "Ціна: $1 назавжди\n\n"
        "Тисни кнопку ↓",
        reply_markup=reply_markup
    )

def main():
    if not TOKEN:
        print("ПОМИЛКА: BOT_TOKEN не встановлено!")
        return

    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))

    print("Бот запущений і працює 24/7!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
