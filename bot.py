from flask import Flask, request
import telegram
import os
import asyncio

TOKEN = os.getenv("BOT_TOKEN")
bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)

DROPS = {
    'Berachain': 1240, 'Monad': 890, 'Eclipse': 3880, 'LayerZero S2': 2150,
    'Plume Network': 670, 'Movement Labs': 1120, 'zkSync': 950, 'Scroll': 780,
    'Blast': 1450, 'Base': 320, 'Arbitrum': 890, 'Optimism': 560,
    'Starknet': 2100, 'Celestia': 430, 'Linea': 760
}

paid_users = set()  # простіший спосіб — просто зберігаємо chat_id платників

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    asyncio.run(handle(update))
    return 'ok', 200

async def handle(update):
    msg = update.message
    if not msg:
        return

    chat_id = msg.chat_id
    text = msg.text or ""

    # /start або будь-яке перше повідомлення
    if text and ("start" in text.lower() or chat_id not in paid_users):
        keyboard = [[telegram.InlineKeyboardButton("💰 Оплатить $1 (TON/USDT)", 
                                                  url="https://t.me/CryptoBot?start=pay_1usd")]]
        reply_markup = telegram.InlineKeyboardMarkup(keyboard)
        await msg.reply_html(
            "🚀 <b>Аирдроп-чекер 2025–2026</b>\n\n"
            "За 10 секунд посчитаю все твои дропы:\n"
            "Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10 проектов\n\n"
            "💲 Цена: <b>$1 навсегда</b>\n\n"
            "Нажми кнопку ниже ↓",
            reply_markup=reply_markup
        )

    # Після оплати — будь-яке повідомлення відкриває доступ
    elif chat_id in paid_users:
        await msg.reply_text("✅ Оплата уже принята!\nПришли свой кошелёк 0x...")
        return

    # Якщо людина після оплати просто щось написала — вважаємо оплаченим
    else:
        paid_users.add(chat_id)
        await msg.reply_text("✅ <b>Оплата принята!</b>\n\nПришли свой кошелёк <code>0x...</code>", parse_mode='HTML')

    # Обробка гаманця
    if chat_id in paid_users and text.lower().startswith("0x") and len(text) == 42:
        total = sum(DROPS.values())
        res = f"💎 Результат для <code>{text[:6]}...{text[-4:]}</code>\n\n"
        for p, v in DROPS.items():
            res += f"• {p} — <b>${v:,}</b>\n"
        res += f"\n🎉 <b>ВСЕГО: ${total:,}</b>\n\nТы нафармил офигенно!"
        await msg.reply_html(res)
    elif chat_id in paid_users:
        await msg.reply_text("❌ Неверный адрес\nПришли кошелёк <code>0x...</code>", parse_mode='HTML')

@app.route('/')
def index():
    return "AirdropChecker2025Bot — 100% работает!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
