from flask import Flask, request
import telegram
import os
import asyncio
import threading

TOKEN = os.getenv("BOT_TOKEN")
app = Flask(__name__)
bot = telegram.Bot(token=TOKEN)

DROPS = {
    'Berachain': 1240, 'Monad': 890, 'Eclipse': 3880, 'LayerZero S2': 2150,
    'Plume Network': 670, 'Movement Labs': 1120, 'zkSync': 950, 'Scroll': 780,
    'Blast': 1450, 'Base': 320, 'Arbitrum': 890, 'Optimism': 560,
    'Starknet': 2100, 'Celestia': 430, 'Linea': 760
}

user_data = {}  # chat_id → {"paid": True/False}

# Асинхронне відправлення
async def send(chat_id, text, markup=None):
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)

def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(coro)

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    if update:
        threading.Thread(target=handle, args=(update,)).start()
    return 'ok', 200

def handle(update):
    async def process():
        try:
            chat_id = None

            # /start
            if update.message and update.message.text and "/start" in update.message.text:
                chat_id = update.message.chat_id
                user_data[chat_id] = {"paid": False}
                keyboard = [[telegram.InlineKeyboardButton("Оплатить $1 (TON/USDT)", url="https://t.me/CryptoBot?start=pay_1usd")]]
                await send(chat_id,
                    "Привет! Самый быстрый аирдроп-чекер 2025–2026\n\n"
                    "За 10 секунд посчитаю все твои дропы по 15+ топ-проектам:\n"
                    "Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n"
                    "Цена: $1 навсегда\n\nЖми кнопку ↓",
                    telegram.InlineKeyboardMarkup(keyboard))

            # Після оплати — будь-яке повідомлення
            elif update.message and update.message.chat_id in user_data:
                chat_id = update.message.chat_id
                if not user_data[chat_id]["paid"]:
                    user_data[chat_id]["paid"] = True
                    await send(chat_id, "Оплата принята! Пришли кошелёк 0x...")

            # Введення гаманця
            elif update.message and update.message.chat_id in user_data and user_data[update.message.chat_id]["paid"]:
                addr = update.message.text.strip()
                chat_id = update.message.chat_id
                if addr.lower().startswith("0x") and len(addr) == 42:
                    total = sum(DROPS.values())
                    res = f"Результаты для {addr[:6]}...{addr[-4:]}:\n\n"
                    for p, v in DROPS.items():
                        res += f"• {p} — ${v:,}\n"
                    res += f"\nВСЕГО: ${total:,}\n\nТы нафармил очень круто!"
                    await send(chat_id, res)
                else:
                    await send(chat_id, "Неправильный адрес Пришли кошелёк 0x...")

        except Exception as e:
            print("Ошибка:", e)

    run_async(process())

@app.route('/')
def index():
    return "Airdrop Checker 2025–2026 — работает!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
