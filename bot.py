from flask import Flask, request
import telegram
import os
import asyncio

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

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    if not update:
        return 'ok', 200

    async def process():
        # /start
        if update.message and update.message.text == "/start":
            chat_id = update.message.chat_id
            user_data[chat_id] = {"paid": False, "waiting": False}
            keyboard = [[telegram.InlineKeyboardButton("Оплатить $1 (TON/USDT)", callback_data="pay")]]
            await bot.send_message(
                chat_id=chat_id,
                text="Привет! Самый быстрый аирдроп-чекер 2025–2026\n\n"
                     "За 10 сек посчитаю все твои дропы по 15+ топ-проектам\n"
                     "Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n"
                     "Цена: $1 навсегда (TON/USDT)\n\nЖми кнопку 👇",
                reply_markup=telegram.InlineKeyboardMarkup(keyboard)
            )

        # кнопка оплати
        if update.callback_query and update.callback_query.data == "pay":
            chat_id = update.callback_query.message.chat_id
            await update.callback_query.answer()
            await bot.send_message(chat_id, "Оплати $1 через @CryptoBot (TON или USDT)\n\n"
                                           "После оплаты пришли сюда любое сообщение (хоть «го»)")
            user_data[chat_id] = {"waiting": True}

        # після оплати
        if update.message and user_data.get(update.message.chat_id, {}).get("waiting"):
            chat_id = update.message.chat_id
            user_data[chat_id]["paid"] = True
            user_data[chat_id]["waiting"] = False
            await bot.send_message(chat_id, "Оплата принята!\nПришли кошелёк 0x...")

        # введення гаманця
        if update.message and user_data.get(update.message.chat_id, {}).get("paid"):
            addr = update.message.text.strip()
            chat_id = update.message.chat_id
            if addr.startswith("0x") and len(addr) == 42:
                total = sum(DROPS.values())
                res = f"Результаты для {addr[:6]}...{addr[-4:]}:\n\n"
                for p, v in DROPS.items():
                    res += f"{p}: ${v:,}\n"
                res += f"\nВСЕГО: ${total:,}\n\nТы нафармил очень круто!"
                await bot.send_message(chat_id, res)
            else:
                await bot.send_message(chat_id, "Неправильный адрес\nПришли кошелёк 0x...")

    asyncio.run(process())
    return 'ok', 200

@app.route('/')
def index():
    return "Bot alive!"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
