from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 5000))

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

DROPS = {
    'Berachain': 1240, 'Monad': 890, 'Eclipse': 3880, 'LayerZero S2': 2150,
    'Plume Network': 670, 'Movement Labs': 1120, 'zkSync': 950, 'Scroll': 780,
    'Blast': 1450, 'Base': 320, 'Arbitrum': 890, 'Optimism': 560,
    'Starknet': 2100, 'Celestia': 430, 'Linea': 760
}

async def start(update, context):
    keyboard = [[InlineKeyboardButton("Оплатить $1 (TON/USDT)", callback_data="pay")]]
    await update.message.reply_text(
        "Привет! Самый быстрый аирдроп-чекер 2025–2026\n\n"
        "За 10 сек посчитаю все твои дропы по 15+ топ-проектам\n"
        "Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n"
        "Цена: $1 навсегда (TON/USDT)\n\n"
        "Жми кнопку 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "pay":
        await query.edit_message_text(
            "Оплати $1 через @CryptoBot (TON или USDT)\n\n"
            "После оплаты пришли сюда любое сообщение (хоть «го»)\n"
            "Я сразу открою доступ"
        )
        context.user_data["waiting"] = True

async def text(update, context):
    text = update.message.text.lower()
    ud = context.user_data

    if ud.get("waiting") or any(x in text for x in ["го", "оплатил", "paid", "готово", "1$"]):
        ud["paid"] = True
        ud["waiting"] = False
        await update.message.reply_text("Оплата принята!\nПришли кошелёк 0x...")
        return

    if ud.get("paid"):
        addr = update.message.text.strip()
        if addr.startswith("0x") and len(addr) == 42:
            total = sum(DROPS.values())
            res = f"Результаты для {addr[:6]}...{addr[-4:]}:\n\n"
            for p, v in DROPS.items():
                res += f"{p}: ${v:,}\n"
            res += f"\nВСЕГО: ${total:,}\n\nТы нафармил очень круто!"
            await update.message.reply_text(res)
        else:
            await update.message.reply_text("Неправильный адрес\nПришли кошелёк 0x...")
    else:
        await update.message.reply_text("Сначала /start и оплати $1")

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        if update:
            application.process_update(update)
        return 'OK', 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return 'Error', 500

@app.route('/')
def index():
    return "Airdrop Checker Bot is running! 🚀"

if __name__ == '__main__':
    print("Бот запущен на webhook — стабильный 24/7!")
    app.run(host="0.0.0.0", port=PORT, debug=False)
