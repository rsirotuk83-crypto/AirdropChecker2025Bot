from flask import Flask, request
import telegram
import os
import asyncio

TOKEN = os.getenv("BOT_TOKEN")
bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)

DROPS = {'Berachain':1240,'Monad':890,'Eclipse':3880,'LayerZero S2':2150,'Plume Network':670,
         'Movement Labs':1120,'zkSync':950,'Scroll':780,'Blast':1450,'Base':320,
         'Arbitrum':890,'Optimism':560,'Starknet':2100,'Celestia':430,'Linea':760}

paid_users = set()

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    asyncio.run(handle(update))
    return 'ok', 200

async def handle(update):
    msg = update.message
    if not msg: return
    chat_id = msg.chat_id
    text = (msg.text or "").strip()

    if "start" in text.lower():
        keyboard = [[telegram.InlineKeyboardButton("Оплатить $1 → TON/USDT",
                                                  url="https://t.me/CryptoBot?start=attach_1_invoice_1_USDT")]]
        await msg.reply_html(
            "Самый быстрый аирдроп-чекер 2025–2026\n\n"
            "За 10 сек посчитаю всё по 15+ проектам\n\n"
            "<b>Цена: $1 навсегда</b>\n\n"
            "Жми кнопку ↓",
            reply_markup=telegram.InlineKeyboardMarkup(keyboard))

    # Після оплати — будь-яке повідомлення = доступ
    elif chat_id not in paid_users:
        paid_users.add(chat_id)
        await msg.reply_html("Оплата принята!\n\nПришли кошелёк <code>0x...</code>")

    # Гаманець
    if chat_id in paid_users and text.lower().startswith("0x") and len(text)==42:
        total = sum(DROPS.values())
        res = f"Результат для <code>{text[:6]}...{text[-4:]}</code>\n\n"
        for p,a in DROPS.items(): res += f"• {p} — <b>${a:,}</b>\n"
        res += f"\n<b>ВСЕГО: ${total:,}</b>\n\nТы красавчик!"
        await msg.reply_html(res)
    elif chat_id in paid_users and text:
        await msg.reply_text("Пришли кошелёк 0x...")

@app.route('/')
def index(): return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
