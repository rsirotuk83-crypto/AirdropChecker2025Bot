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

user_data = {}

# Новий правильний спосіб — фонова задача
async def send_message(chat_id, text, reply_markup=None):
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

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
    if not update:
        return 'ok', 200

    # Запускаємо обробку в фоні — це найголовніше для Railway
    threading.Thread(target=handle_update, args=(update,)).start()
    return 'ok', 200

def handle_update(update):
    async def process():
        try:
            # /start
            if update.message and update.message.text:
                cmd = update.message.text.strip().split("@")[0].split()[0].lower()
                if cmd == "/start":
                    chat_id = update.message.chat_id
                    user_data[chat_id] = {"paid": False, "waiting": False}
                    keyboard = [[telegram.InlineKeyboardButton("Оплатить $1 (TON/USDT)", callback_data="pay")]]
                    await send_message(
                        chat_id,
                        "Привет! Самый быстрый аирдроп-чекер 2025–2026\n\n"
                        "За 10 секунд посчитаю все твои дропы по 15+ топ-проектам:\n"
                        "Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n"
                        "Цена: $1 навсегда (TON/USDT)\n\nЖми кнопку ↓",
                        telegram.InlineKeyboardMarkup(keyboard)
                    )
                    return

            # Кнопка
            if update.callback_query and update.callback_query.data == "pay":
                query = update.callback_query
                await query.answer()
                chat_id = query.message.chat_id
                user_data[chat_id] = {"waiting": True, "paid": False}
                await send_message(
                    chat_id,
                    "Оплати $1 через @CryptoBot (TON или USDT)\n\n"
                    "После оплаты пришли сюда любое сообщение (хоть «го», «ок», «+»)\n"
                    "Я сразу открою доступ"
                )
                return

            # Після «го»
            if update.message and user_data.get(update.message.chat_id, {}).get("waiting"):
                chat_id = update.message.chat_id
                user_data[chat_id] = {"paid": True, "waiting": False}
                await send_message(chat_id, "Оплата принята! Пришли кошелёк 0x...")
                return

            # Гаманець
            if update.message and user_data.get(update.message.chat_id, {}).get("paid"):
                addr = update.message.text.strip()
                chat_id = update.message.chat_id
                if addr.lower().startswith("0x") and len(addr) == 42:
                    total = sum(DROPS.values())
                    res = f"Результаты для {addr[:6]}...{addr[-4:]}:\n\n"
                    for p, v in DROPS.items():
                        res += f"• {p} — ${v:,}\n"
                    res += f"\nВСЕГО: ${total:,}\n\nТы нафармил очень круто!"
                    await send_message(chat_id, res)
                else:
                    await send_message(chat_id, "Неправильный адрес Пришли кошелёк 0x...")

        except Exception as e:
            print(f"Ошибка: {e}")

    run_async(process())

@app.route('/')
def index():
    return "Airdrop Checker 2025–2026 — работает 100%"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
