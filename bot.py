from flask import Flask, request, jsonify
import telegram
import os

TOKEN = os.getenv("BOT_TOKEN")
bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        update = telegram.Update.de_json(request.get_json(force=True), bot)
        if update.message:
            chat_id = update.message.chat_id
            text = update.message.text or ""

            # Головне меню з кнопкою оплати
            keyboard = [[telegram.InlineKeyboardButton("Оплатить $1 → TON/USDT",
                 url="https://t.me/CryptoBot?start=IVeOWQMbUYjt")]]
            reply_markup = telegram.InlineKeyboardMarkup(keyboard)

            bot.send_message(
                chat_id=chat_id,
                text="Самый быстрый аирдроп-чекер 2025–2026\n\n"
                     "За 10 сек посчитаю всё по 15+ топ-проектам\n\n"
                     "Цена: $1 навсегда\n\nЖми кнопку ↓",
                reply_markup=reply_markup
            )
        return jsonify(success=True)  # важливо!

@app.route('/')
def index():
    return "Бот работает!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))
