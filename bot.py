import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

# Сума дропів (можеш міняти)
DROPS = {
    'Berachain': 1240,
    'Monad': 890,
    'Eclipse': 3880,
    'LayerZero S2': 2150,
    'Plume Network': 670,
    'Movement Labs': 1120,
    'zkSync': 950,
    'Scroll': 780,
    'Blast': 1450,
    'Base': 320,
    'Arbitrum': 890,
    'Optimism': 560,
    'Starknet': 2100,
    'Celestia': 430,
    'Linea': 760,
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("💰 Оплатить $1 (TON/USDT)", callback_data="pay")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🚀 Привет! Я самый быстрый аирдроп-чекер 2025–2026\n\n"
        "За 10 секунд посчитаю твои дропы по 15+ топовым проектам:\n"
        "Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n"
        "💲 Цена: $1 навсегда (TON/USDT)\n"
        "После оплаты — доступ навсегда\n\n"
        "Жми кнопку ниже 👇",
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "pay":
        await query.edit_message_text(
            "💳 Оплати $1 через @CryptoBot (TON или USDT)\n\n"
            "После оплаты пришли сюда любое сообщение (хоть «го», хоть «оплатил»)\n"
            "Я сразу дам доступ 🔥"
        )
        context.user_data["waiting"] = True

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    user_data = context.user_data

    # Чекаємо оплату
    if user_data.get("waiting") or any(x in text for x in ["оплатил", "paid", "го", "готово", "оплата", "1$"]):
        user_data["paid"] = True
        user_data["waiting"] = False
        await update.message.reply_text("✅ Оплата прошла!\nПришли свой кошелёк (0x...)")
        return

    # Вже оплатив — чекаємо адресу
    if user_data.get("paid"):
        addr = update.message.text.strip()
        if addr.startswith("0x") and len(addr) == 42:
            total = sum(DROPS.values())
            result = f"📊 Результаты для {addr[:6]}...{addr[-4:]}:\n\n"
            for name, amount in DROPS.items():
                result += f"{name}: ${amount:,}\n"
            result += f"\n🔥 ВСЕГО: ${total:,}\n\nТы нафармил очень круто!"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("❌ Неверный адрес\nПришли кошелёк в формате 0x...")
    else:
        await update.message.reply_text("Сначала нажми /start и оплати $1 😉")

async def main():
    app = Application.builder().token(TOKEN).read_timeout(30).write_timeout(30).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Бот запущен и работает 24/7! @AirdropChecker2025Bot")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    
    # Тримаємо процес живим (обов’язково для Railway!)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
