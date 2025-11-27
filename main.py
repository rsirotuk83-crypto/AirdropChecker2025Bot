import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")          # твій токен бота
ADMIN_ID = 777777777                     # ←←←←←←←←←←←←←←←←←← ЗАМІНИ НА СВІЙ ID (від @userinfobot)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or "без юзернейму"

    # кнопка з твоїм рефералкою + ID юзера (щоб ти бачив хто оплатив)
    keyboard = [[InlineKeyboardButton("Оплатить $1 → TON/USDT",
                                     url=f"https://t.me/CryptoBot?start=IVeOWQMbUYjt_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Самый быстрый аирдроп-чекер 2025–2026\n\n"
        "За 10 сек посчитаю всё по 15+ топ-проектам\n\n"
        "Цена: $1 навсегда\n\n"
        "Жми кнопку ↓",
        reply_markup=reply_markup
    )

    # сповіщення тобі в ЛС
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Новий юзер!\n\nID: {user_id}\nЮзернейм: @{username}\nІм’я: {user.full_name}"
    )


def main():
    app = Application.builder().token(TOKEN).build()

    # реагує на /start і на кнопку «СТАРТ» внизу
    app.add_handler(CommandHandler("start", start))
    # реагує на будь-яке текстове повідомлення (привіт, хай, 123 і т.д.)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))

    print("Бот запущений і працює!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
