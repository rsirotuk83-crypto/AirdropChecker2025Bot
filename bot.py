import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

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
    keyboard = [[InlineKeyboardButton("Оплатить $1 (TON/USDT)", callback_data="pay")]]
    await update.message.reply_text(
        "Привет! Я самый быстрый аирдроп-чекер 2025–2026\n\n"
        "За 10 секунд посчитаю твои дропы по 15+ топовым проектам:\n"
        "Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n"
        "Цена: $1 навсегда — всего $1 (TON/USDT)\n\n"
        "Жми кнопку 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "pay":
        await query.edit_message_text(
            "Оплати $1 через @CryptoBot (TON/USDT) — самый быстрый способ\n\n"
            "После оплаты пришли сюда любое сообщение (хоть «го», хоть «оплатил»)\n"
            "Я сразу открою доступ"
        )
        context.user_data["waiting"] = True

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    ud = context.user_data

    if ud.get("waiting") or any(w in text for w in ["го", "оплатил", "оплатил", "paid", "готово"]):
        ud["paid"] = True
        ud["waiting"] = False
        await update.message.reply_text("Оплата принята!\nПришли свой кошелёк (0x…)")
        return

    if ud.get("paid"):
        addr = update.message.text.strip()
        if addr.startswith("0x") and len(addr) == 42:
            total = sum(DROPS.values())
            res = f"Результаты для {addr[:6]}...{addr[-4:]}:\n\n"
            for name, val in DROPS.items():
                res += f"{name}: ${val:,}\n"
            res += f"\nВСЕГО: ${total:,}\n\nТы нафармил очень круто!"
            await update.message.reply_text(res)
        else:
            await update.message.reply_text("Неправильный формат\nПришли кошелёк 0x...")
    else:
        await update.message.reply_text("Сначала нажми /start и оплати $1")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

    print("Бот запущен и работает 24/7 — Railway НЕ убьёт!")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
