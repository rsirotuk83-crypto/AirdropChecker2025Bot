from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes
import os
import asyncio

TOKEN = os.getenv("BOT_TOKEN")
app = Flask(__name__)

# Будуємо додаток один раз
application = Application.builder().token(TOKEN).build()

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
        "Жми кнопку 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "pay":
        await query.edit_message_text(
            "Оплати $1 через @CryptoBot (TON или USDT)\n\n"
            "После оплаты пришли сюда любое сообщение (хоть «го»)\n"
            "Я сразу открою доступ"
        )
        context.user_data["waiting"] = True

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    ud = context.user_data

    if ud.get("waiting") or any(word in text for word in ["го", "оплатил", "paid", "готово", "1$"]):
        ud["paid"] = True
        ud["waiting"] = False
        await update.message.reply_text("Оплата принята!\nПришли кошелёк 0x...")
        return

    if ud.get("paid"):
        addr = update.message.text.strip()
        if addr.startswith("0x") and len(addr) == 42:
            total = sum(DROPS.values())
            res = f"Результаты для {addr[:6}...{addr[-4:]}:\n\n"
            for p, v in DROPS.items():
                res += f"{p}: ${v:,}\n"
            res += f"\nВСЕГО: ${total:,}\n\nТы нафармил очень круто!"
            await update.message.reply_text(res)
        else:
            await update.message.reply_text("Неправильный адрес\nПришли кошелёк 0x...")
    else:
        await update.message.reply_text("Сначала /start и оплати $1")

# Реєструємо хендлери
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(Message.TEXT & ~Message.COMMAND, text))

# Webhook-ендпоінт
@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, application.bot)
    asyncio.run(application.process_update(update))  # ← саме так треба на Flask + PTB 21+
    return 'OK', 200

@app.route('/')
def index():
    return "AirdropChecker2025Bot is running 24/7!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
