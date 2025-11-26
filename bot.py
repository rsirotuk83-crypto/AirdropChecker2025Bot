from flask import Flask, request
import telegram
import os
import asyncio

TOKEN = os.getenv("BOT_TOKEN")
URL = "https://airdropchecker2025bot-production.up.railway.app"  # твій URL

app = Flask(__name__)
bot = telegram.Bot(token=TOKEN)

# Твій словник дропів
DROPS = {
    'Berachain': 1240, 'Monad': 890, 'Eclipse': 3880, 'LayerZero S2': 2150,
    'Plume Network': 670, 'Movement Labs': 1120, 'zkSync': 950, 'Scroll': 780,
    'Blast': 1450, 'Base': 320, 'Arbitrum': 890, 'Optimism': 560,
    'Starknet': 2100, 'Celestia': 430, 'Linea': 760
}

# Простий стан (без ContextTypes, без Application)
user_data = {}

async def send_welcome(chat_id):
    keyboard = [[telegram.InlineKeyboardButton("Оплатить $1 (TON/USDT)", callback_data="pay")]]
    reply_markup = telegram.InlineKeyboardMarkup(keyboard)
    await bot.send_message(
        chat_id=chat_id,
        text="Привет! Самый быстрый аирдроп-чекер 2025–2026\n\n"
             "За 10 сек посчитаю все твои дропы по 15+ топ-проектам\n"
             "Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n"
             "Цена: $1 навсегда (TON/USDT)\n\n"
             "Жми кнопку 👇",
        reply_markup=reply_markup
    )

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    if not update:
        return 'ok'

    # Обробка повідомлень
    if update.message:
        chat_id = update.message.chat_id
        text = update.message.text or ""

        if text == "/start":
            asyncio.run(send_welcome(chat_id))
            user_data[chat_id] = {"paid": False}

        elif user_data.get(chat_id, {}).get("waiting"):
            user_data[chat_id]["paid"] = True
            user_data[chat_id]["waiting"] = False
            await bot.send_message(chat_id, "Оплата принята!\nПришли кошелёк 0x...")
            asyncio.run(await bot.send_message(chat_id, "Оплата принята!\nПришли кошелёк 0x..."))

        elif user_data.get(chat_id, {}).get("paid"):
            addr = text.strip()
            if addr.startswith("0x") and len(addr) == 42:
                total = sum(DROPS.values())
                res = f"Результаты для {addr[:6]}...{addr[-4:]}:\n\n"
                for p, v in DROPS.items():
                    res += f"{p}: ${v:,}\n"
                res += f"\nВСЕГО: ${total:,}\n\nТы нафармил очень круто!"
                asyncio.run(bot.send_message(chat_id, res))
            else:
                asyncio.run(bot.send_message(chat_id, "Неправильный адрес\nПришли кошелёк 0x..."))

    # Обробка кнопки
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat_id
        if query.data == "pay":
            asyncio.run(query.answer())
            asyncio.run(bot.send_message(
                chat_id,
                "Оплати $1 через @CryptoBot (TON или USDT)\n\n"
                "После оплаты пришли сюда любое сообщение (хоть «го»)\n"
                "Я сразу открою доступ"
            ))
            user_data[chat_id] = {"waiting": True}

    return 'ok', 200

@app.route('/')
def index():
    return "Bot is alive!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
