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

user_data = {}  # chat_id → {"paid": False}

async def send(chat_id, text, markup=None):
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup, parse_mode='HTML')

def run_async(coro):
    loop = asyncio.get_event_loop_policy().get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(coro)

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    if update and update.message:
        threading.Thread(target=handle, args=(update.message,)).start()
    return 'ok', 200

def handle(msg):
    async def process():
        chat_id = msg.chat_id
        text = msg.text or ""

        # /start — перше повідомлення
        if "/start" in text:
            user_data[chat_id] = {"paid": False}
            keyboard = [[telegram.InlineKeyboardButton("💸 Оплатить $1 (TON/USDT)", 
                                                      url="https://t.me/CryptoBot?start=pay_1usd")]]
            await send(chat_id,
                "🚀 <b>Аирдроп-чекер 2025–2026</b>\n\n"
                "За 10 секунд посчитаю все твои дропы по 15+ топ-проектам:\n"
                "Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n"
                "💰 Цена: <b>$1 навсегда</b>\n\n"
                "Нажми кнопку ниже ↓",
                telegram.InlineKeyboardMarkup(keyboard))

        # Після оплати — будь-яке повідомлення відкриває доступ
        elif chat_id in user_data and not user_data[chat_id]["paid"]:
            user_data[chat_id]["paid"] = True
            await send(chat_id, "✅ <b>Оплата принята!</b>\n\nПришли свой кошелёк <code>0x...</code>")

        # Введення гаманця
        elif chat_id in user_data and user_data[chat_id]["paid"]:
            addr = text.strip()
            if addr.lower().startswith("0x") and len(addr) == 42:
                total = sum(DROPS.values())
                res = f"💎 Результат для <code>{addr[:6]}...{addr[-4:]}</code>\n\n"
                for project, amount in DROPS.items():
                    res += f"• {project} — <b>${amount:,}</b>\n"
                res += f"\n🎉 <b>ВСЕГО: ${total:,}</b>\n\nТы нафармил офигенно!"
                await send(chat_id, res)
            else:
                await send(chat_id, "❌ Неверный адрес\nПришли кошелёк в формате <code>0x...</code>")

    run_async(process())

@app.route('/')
def index():
    return "AirdropChecker2025Bot — работает на максималках 🔥"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
