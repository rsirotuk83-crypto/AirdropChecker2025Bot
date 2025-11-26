from flask import Flask, request
import telegram
import os
import asyncio
import logging

logging.getLogger("httpx").setLevel(logging.WARNING)

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

# Фікс для Railway
if asyncio.get_event_loop().is_closed():
    asyncio.set_event_loop(asyncio.new_event_loop())
loop = asyncio.get_event_loop()

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    if not update:
        return 'ok', 200

    def run():
        async def handle():
            try:
                # 1. /start
                if update.message and update.message.text:
                    cmd = update.message.text.strip().split("@")[0].split()[0]
                    if cmd == "/start":
                        chat_id = update.message.chat_id
                        user_data[chat_id] = {"paid": False, "waiting": False}
                        keyboard = [[telegram.InlineKeyboardButton("Оплатить $1 (TON/USDT)", callback_data="pay")]]
                        await bot.send_message(
                            chat_id=chat_id,
                            text="Привет! Самый быстрый аирдроп-чекер 2025–2026\n\n"
                                 "За 10 секунд посчитаю все твои дропы по 15+ топ-проектам:\n"
                                 "Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n"
                                 "Цена: $1 навсегда (TON/USDT)\n\nЖми кнопку ↓",
                            reply_markup=telegram.InlineKeyboardMarkup(keyboard)
                        )
                        return

                # 2. Кнопка «Оплатить»
                if update.callback_query and update.callback_query.data == "pay":
                    query = update.callback_query
                    await query.answer()
                    await bot.send_message(
                        chat_id=query.message.chat_id,
                        text="Оплати $1 через @CryptoBot (TON или USDT)\n\n"
                             "После оплаты пришли сюда любое сообщение (хоть «го», «ок», «+»)\n"
                             "Я сразу открою доступ"
                    )
                    user_data[query.message.chat_id] = {"waiting": True, "paid": False}
                    return

                # 3. Після оплати — будь-яке повідомлення
                if update.message and user_data.get(update.message.chat_id, {}).get("waiting"):
                    chat_id = update.message.chat_id
                    user_data[chat_id] = {"paid": True, "waiting": False}
                    await bot.send_message(chat_id=chat_id, text="Оплата принята! Пришли кошелёк 0x...")
                    return

                # 4. Введення гаманця
                if update.message and user_data.get(update.message.chat_id, {}).get("paid"):
                    addr = update.message.text.strip()
                    chat
