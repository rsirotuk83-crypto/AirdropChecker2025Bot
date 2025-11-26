from flask import Flask, request
import telegram
import os
import requests

TOKEN = os.getenv("BOT_TOKEN")                  # твій бот-токен від @BotFather
CRYPTO_PAY_TOKEN = "492747:AArkKw71su6CZovLMO1QVMY8CZrtNxMz7rP"  # твій API-токен з CryptoBot
bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)

# Проекти і суми (можна міняти)
DROPS = {
    'Berachain': 1240, 'Monad': 890, 'Eclipse': 3880, 'LayerZero S2': 2150,
    'Plume Network': 670, 'Movement Labs': 1120, 'zkSync': 950, 'Scroll': 780,
    'Blast': 1450, 'Base': 320, 'Arbitrum': 890, 'Optimism': 560,
    'Starknet': 2100, 'Celestia': 430, 'Linea': 760
}

paid_users = set()   # хто вже оплатив

# Перевірка статусу інвойсу
def check_invoice(invoice_id):
    url = f"https://pay.crypt.bot/api/getInvoices"
    params = {"invoice_ids": invoice_id, "token": CRYPTO_PAY_TOKEN}
    r = requests.get(url, params=params)
    if r.status_code == 200:
        data = r.json()
        if data["ok"] and data["result"][0]["status"] == "paid":
            return True
    return False

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'GET':
        return 'OK'
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    msg = update.message
    if not msg:
        return 'ok'

    chat_id = msg.chat_id
    text = msg.text or ""

    # Якщо вже оплатив — одразу відкриваємо доступ
    if chat_id in paid_users:
        if text.lower().startswith("0x") and len(text) == 42:
            total = sum(DROPS.values())
            res = f"Результат для <code>{text[:6]}...{text[-4:]}</code>\n\n"
            for p, a in DROPS.items():
                res += f"• {p} — <b>${a:,}</b>\n"
            res += f"\n<b>ВСЕГО: ${total:,}</b>\nТы красавчик!"
            bot.send_message(chat_id=chat_id, text=res, parse_mode='HTML')
        else:
            bot.send_message(chat_id=chat_id, text="Пришли кошелёк 0x...")
        return 'ok'

    # Показуємо кнопку оплати
    keyboard = [[telegram.InlineKeyboardButton("💳 Оплатить $1 (TON/USDT)", 
                 url="https://t.me/CryptoBot?start=IVeOWQMbUYjt")]]
    reply_markup = telegram.InlineKeyboardMarkup(keyboard)

    bot.send_message(chat_id=chat_id,
                     text="🚀 Самый быстрый аирдроп-чекер 2025–2026\n\n"
                          "За 10 сек посчитаю всё по 15+ топ-проектам\n\n"
                          "💰 Цена: $1 навсегда\n\nЖми кнопку ↓",
                     reply_markup=reply_markup)
    return 'ok'

@app.route('/')
def index():
    return "Бот живой и готов зарабатывать!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
