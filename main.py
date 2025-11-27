from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 777777777  # ← ТУТ ТВІЙ ID (від @userinfobot)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [[InlineKeyboardButton("Оплатить $1 → TON/USDT", 
                                     url=f"https://t.me/CryptoBot?start=IVeOWQMbUYjt_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Самый быстрый аирдроп-чекер 2025–2026\n\n"
        "За 10 сек посчитаю всё по 15+ топ-проектам\n\n"
        "Цена: $1 навсегда\n\nЖми кнопку ↓",
        reply_markup=reply_markup
    )
    
    # повідомлення адміну
    await context.bot.send_message(ADMIN_ID, f"Новий юзер: {user_id}\n@{update.effective_user.username}")

application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))
application.run_polling(drop_pending_updates=True)
