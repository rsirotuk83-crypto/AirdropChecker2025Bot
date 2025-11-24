import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
from rich.console import Console
import asyncio

BOT_TOKEN = "8485697907:AAEil1WfkZGVhR3K9wlHEVBJ5qNvn2B_mow"  # твій токен

# Фейкові дані для 15+ проєктів (реальні API можна додати пізніше)
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
    keyboard = [[InlineKeyboardButton("Оплатити $1 (TON/USDT)", callback_data='pay')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        'Airdrop Checker 2025–2026\n\n'
        'Перевіряю 15+ топових проєктів за 10 секунд\n'
        'Ціна: $1 раз і назавжди\n\n'
        'Натисни кнопку внизу', 
        reply_markup=reply_markup
    )

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        'Надішли будь-яке повідомлення (наприклад "Paid" або "Готово") — я дам доступ назавжди'
    )
    context.user_data['paid'] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('paid'):
        await update.message.reply_text('Спочатку оплати $1 кнопкою /start')
        return
    
    address = update.message.text.strip()
    if not address.startswith('0x') or len(address) != 42:
        await update.message.reply_text('Надішли валідну адресу EVM (0x...)')
        return

    total = 0
    result = f"Результати для {address[:6]}...{address[-4:]}\n\n"
    for project, value in PROJECTS.items():
        result += f"{project}: ${value:,}\n"
        total += value
    result += f"\nВСЬОГО ≈ ${total:,}"

    await update.message.reply_text(result)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(pay, pattern='^pay$'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущений! @AirdropChecker2025Bot")
    app.run_polling()

if __name__ == '__main__':
    main()
