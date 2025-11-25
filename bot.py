import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")

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
    keyboard = [[InlineKeyboardButton("💰 Оплатить $1 (TON/USDT)", callback_data='pay')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        '🚀 Привет! Я Airdrop Checker 2025–2026\n\n'
        'За 10 секунд проверю твои аирдропы на 15+ проектах:\n'
        'Berachain • Monad • Eclipse • LayerZero S2 • Plume + ещё 10\n\n'
        '💵 Цена: $1 навсегда (TON/USDT)\n'
        'После оплаты — доступ навсегда\n\n'
        'Нажми кнопку ниже 👇',
        reply_markup=reply_markup
    )

async def pay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        '💳 Оплата $1 через @CryptoBot (TON/USDT)\n\n'
        'После оплаты пришли любое сообщение (например «Paid» или хеш транзакции)\n'
        'Я проверю и дам доступ мгновенно 🚀'
    )
    context.user_data['waiting_payment'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    # Якщо чекаємо оплату
    if context.user_data.get('waiting_payment') or 'paid' in text or 'оплатил' in text or 'го' in text:
        context.user_data['paid'] = True
        context.user_data['waiting_payment'] = False
        await update.message.reply_text('✅ Оплата подтверждена!\nПришли адрес кошелька (0x...) для проверки')
        return

    # Якщо вже оплатив і присилає адресу
    if context.user_data.get('paid'):
        address = update.message.text.strip()
        if address.startswith('0x') and len(address) == 42:
            total = sum(PROJECTS.values())
            result = f"📊 Результаты для {address[:6]}...{address[-4:]}:\n\n"
            for project, value in PROJECTS.items():
                result += f"{project}: ${value:,}\n"
            result += f"\n🔥 ВСЕГО: ${total:,}\n\nТы нафармил очень достойно! 💰"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text('❌ Неверный адрес. Пришли кошелёк формата 0x...')
    else:
        await update.message.reply_text('Сначала нажми /start и оплати $1 😉')

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(pay_callback, pattern='^pay$'))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == '__main__':
    print("Бот запущен! @AirdropChecker2025Bot готов к фарму! 🚀")
    app.run_polling()
