import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext

TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_PARAM = "IVeOWQMbUYjt"   # твій параметр з CryptoBot

# тут зберігатимемо хто вже оплатив (в пам'яті, перезапуститься — список очиститься, але на старті норм)
PAID_USERS = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # якщо вже оплатив — одразу даємо доступ
    if user_id in PAID_USERS:
        await update.message.reply_text(
            "Доступ вже відкрито назавжди!\n\n"
            "Тут буде твій чекер або інструкція.\n"
            "Поки що — вітаю з покупкою!"
        )
        return

    # звичайна кнопка оплати з параметром + ID юзера
    keyboard = [[InlineKeyboardButton("Оплатить $1 → TON/USDT",
                                     url=f"https://t.me/CryptoBot?start={CRYPTOBOT_PARAM}_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Найшвидший аирдроп-чекер 2025–2026\n\n"
        "За 10 сек порахую все по 15+ топ-проектам\n\n"
        "Ціна: $1 назавжди\n\n"
        "Тисни кнопку ↓",
        reply_markup=reply_markup
    )

# обробка пре-чек ауту від CryptoBot (коли юзер натиснув кнопку)
async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # нічого не робимо — просто дозволяємо оплату

# коли оплата пройшла — CryptoBot шле повідомлення з payload = user_id
async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = int(update.message.successful_payment.invoice_payload)
    PAID_USERS.add(user_id)

    await update.message.reply_text(
        "Оплата пройшла успішно!\n\n"
        "Доступ відкрито назавжди!\n"
        "Твій аирдроп-чекер вже тут (або посилання/інструкція).\n"
        "Вітаю!"
    )

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start))
    # обов’язково для CryptoBot payments
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    print("Бот запущений — автоматична оплата працює!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
