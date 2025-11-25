from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")
app = Flask(__name__)

application = Application.builder().token(TOKEN).build()

DROPS = {
    'Berachain': 1240, 'Monad': 890, 'Eclipse': 3880, 'LayerZero S2': 2150,
    'Plume Network': 670, 'Movement Labs': 1120, 'zkSync': 950, 'Scroll': 780,
    'Blast': 1450, 'Base': 320, 'Arbitrum': 890, 'Optimism': 560,
    'Starknet': 2100, 'Celestia': 430, 'Linea': 760
}

async def start(update, context):
    keyboard = [[{"text": "Оплатить $1 (TON/USDT)", "callback_data": "pay"}]]
    await update.message.reply_text(
        "Привет! Самый быстрый аирдроп-чекер 2025–2026\n\n"
        "За 10 сек посчитаю все твои дропы по 15+ топ-проектам\n\n"
        "Цена: $1 навсегда\nЖми кнопку 👇",
        reply_markup={"inline_keyboard": keyboard}
    )

async def button(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "pay":
        await query.edit_message_text(
            "Оплати $1 в @CryptoBot (TON/USDT)\nПосле оплаты пришли любое сообщение — я открою доступ"
        )
        context.user_data["waiting"] = True

async def text(update, context):
    if context.user_data.get("waiting") or "го" in update.message.text.lower():
        context.user_data["paid"] = True
        context.user_data["waiting"] = False
        await update.message.reply_text("Оплата принята!\nПришли кошелёк 0x...")
        return
    if context.user_data.get("paid"):
        addr = update.message.text.strip()
        if addr.startswith("0x") and len(addr) == 42:
            total = sum(DROPS.values())
            res = f"Результаты для {addr[:6]}...{addr[-4:]}:\n\n"
            for name, amount in DROPS.items():
                res += f"• {name}: ${amount:,}\n"
            res += f"\nВСЕГО: ${total:,}\nТы нафармил очень круто!"
            await update.message.reply_text(res)
        else:
            await update.message.reply_text("Неправильный адрес\nПришли кошелёк 0x...")

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    if request.method == 'POST':
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.process_update(update)
        return 'OK'
    else:
        abort(403)

@app.route('/')
def index():
    return "Бот живой!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
