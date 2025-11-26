from flask import Flask, request
import telegram
import os

TOKEN = os.getenv("BOT_TOKEN")
bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)

DROPS = {'Berachain':1240,'Monad':890,'Eclipse':3880,'LayerZero S2':2150,'Plume Network':670,
         'Movement Labs':1120,'zkSync':950,'Scroll':780,'Blast':1450,'Base':320,
         'Arbitrum':890,'Optimism':560,'Starknet':2100,'Celestia':430,'Linea':760}

paid_users = set()   # тут зберігаємо хто вже оплатив

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

    # /start — головне меню з кнопкою
    if text.lower().startswith('/start') or chat_id not in paid_users:
        keyboard = [[telegram.InlineKeyboardButton("Оплатить $1 → TON/USDT", 
                                                  url="https://t.me/CryptoBot?start=attach_1_invoice_1_USDT")]]
        bot.send_message(chat_id=chat_id,
                         text="Самый быстрый аирдроп-чекер 2025–2026\n\n"
                              "За 10 сек посчитаю всё по 15+ топ-проектам\n\n"
                              "Цена: $1 навсегда\n\nЖми кнопку ↓",
                         reply_markup=telegram.InlineKeyboardMarkup(keyboard))
        return 'ok'

    # Після оплати — будь-яке повідомлення = доступ відкрито
    if chat_id not in paid_users:
        paid_users.add(chat_id)
        bot.send_message(chat_id=chat_id, text="Оплата принята! ✅\n\nПришли кошелёк 0x...")
        return 'ok'

    # Введення гаманця
    if text.lower().startswith("0x") and len(text) == 42:
        total = sum(DROPS.values())
        res = f"Результат для {text[:6]}...{text[-4:]}\n\n"
        for p, a in DROPS.items():
            res += f"• {p} — ${a:,}\n"
        res += f"\nВСЕГО: ${total:,}\nТы нафармил офигенно!"
        bot.send_message(chat_id=chat_id, text=res)
    else:
        bot.send_message(chat_id=chat_id, text="Неправильный адрес\nПришли кошелёк 0x...")

    return 'ok'

@app.route('/')
def index():
    return "Бот работает 100%"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
