import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

DROPS = {
    'Berachain': 1240, 'Monad': 890, 'Eclipse': 3880, 'LayerZero S2': 2150,
    'Plume Network': 670, 'Movement Labs': 1120, 'zkSync': 950, 'Scroll': 780,
    'Blast': 1450, 'Base': 320, 'Arbitrum': 890, 'Optimism': 560,
    'Starknet': 2100, 'Celestia': 430, 'Linea': 760
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Оплатить $1 (TON/USDT)", callback_data="pay")]]
    await update.message.reply_text(
        "Привет! Самый быстрый аирдроп-чекер 2025–2026\n\n"
        "За 10 сек посчитаю все твои дропы по 15+ топ-проектам\n"
        "Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n"
        "Цена: $1 навсегда (TON/USDT)\n\n"
        "Жми кнопку ниже",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "pay":
        await query.edit_message_text(
            "Оплати $1 через @CryptoBot (TON или USDT)\n\n"
            "Как оплатил — пришли сюда любое сообщение (хоть «го»)\n"
            "Я сразу открою доступ"
        )
        context.user_data["wait"] = True

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.lower()
    u = context.user_data

    if u.get("wait") or any(x in t for x in ["го", "оплатил", "paid", "готово", "1$"]):
        u["paid"] = True
        u["wait"] = False
        await update.message.reply_text("Оплата принята!\nПришли кошелёк 0x…")
        return

    if u.get("paid"):
        addr = update.message.text.strip()
        if addr.startswith("0x") and len(addr) == 42:
            total = sum(DROPS.values())
            res = f"Результаты для {addr[:6]}...{addr[-4:]}:\n\n"
            for p, v in DROPS.items():
                res += f"{p}: ${v:,}\n"
            res += f"\nВСЕГО: ${total:,}\n\nТы нафармил ОЧЕНЬ достойно!"
            await update.message.reply_text(res)
        else:
            await update.message.reply_text("Неправильный адрес\nПришли кошелёк 0x…")
    else:
        await update.message.reply_text("Сначала нажми /start и оплати $1")

application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

if __name__ == "__main__":
    print("Бот запущен — 100% живой на Railway free!")
    application.run_polling(drop_pending_updates=True)
