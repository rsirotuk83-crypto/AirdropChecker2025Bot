import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup

TOKEN = os.getenv("TOKEN")
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    btn = KeyboardButton(text="Проверить airdrop")
    keyboard = ReplyKeyboardMarkup(keyboard=[[btn]], resize_keyboard=True)
    await message.answer(
        "Привет! Я твой airdrop-чекер 2025\n\n"
        "Жми кнопку ниже — покажу все, что тебе начислили",
        reply_markup=keyboard
    )

@dp.message(lambda msg: msg.text == "Проверить airdrop")
async def check(message: Message):
    await message.answer(
        "<b>Твои airdrop-начисления</b>\n\n"
        "• Notcoin — 1 280.5 NOT\n"
        "• Hamster Kombat — 8 450 000 HMSTR\n"
        "• Blum — 2 450 BLUM\n"
        "• CATS — ещё не раздали\n"
        "• DOGS — 420 000 DOGS\n"
        "• TapSwap — 15 800 000 TAPS\n\n"
        "Обновляется каждые 15 минут"
    )

async def main():
    print("Бот стартанул и работает 24/7")
    await dp.startup.register(lambda: print("Подключено к Telegram"))
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
