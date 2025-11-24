import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import asyncio

# Твій токен
BOT_TOKEN = "8485697907:AAEil1WfkZGVhR3K9wlHEVBJ5qNvn2B_mow"

# Дані для 15+ проєктів (фейкові для прикладу, можна замінити на реальні API)
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("💰 Оплатити $1 (TON/USDT)", callback_data='pay')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        '🚀 Привіт! Я Airdrop Checker 2025 Bot.\n\n'
        'За 10 секунд перевірю твої аірдропи на 15+ проєктах:\n'
        'Berachain • Monad • Eclipse • LayerZero S2 • Plume + ще 10!\n\n'
        '💵 Ціна: $1 разово (TON/USDT через @CryptoBot).\n'
        'Після оплати — сканую назавжди.\n\n'
        'Натисни кнопку нижче 👇', reply_markup=reply_markup
    )

async def pay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        '💳 Оплата $1 через @CryptoBot.\n\n'
        'Надішли мені підтвердження (наприклад, "Paid" або tx-хеш).\n'
        'Я перевірю і дам доступ! 🚀'
    )
    context.user_data['paid'] = True  # Для тесту — відразу даємо доступ

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if context.user_data.get('paid') or 'paid' in text.lower() or 'tx' in text.lower():
        await update.message.reply_text('✅ Оплата підтверджена! Надішли адресу гаманця (0x...) для скану.')
        context.user_data['paid'] = True
        return

    if context.user_data.get('paid'):
        address = text.strip()
        if address.startswith('0x') and len(address) == 42:
            total = 0
            result = f"📊 Результати для {address[:6]}...{address[-4:]}:\n\n"
            for project, value in PROJECTS.items():
                result += f"{project}: ${value:,}\n"
                total += value
            result += f"\n🔥 ВСЬОГО: ${total:,}\n\nТи нафармив солідно! 🚀"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text('❌ Невірна адреса. Спробуй ще раз (0x...).')
    else:
        await update.message.reply_text('Спочатку /start і оплати $1.')

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(pay_callback, pattern='^pay$'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущений! @AirdropChecker2025Bot готовий до фарму! 💰")
    app.run_polling()

if __name__ == '__main__':
    main()
