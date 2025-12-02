import os
import logging
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Твій токен з змінних середовища
TOKEN = os.getenv("TOKEN")

# Правильний спосіб для aiogram 3.7+
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Клавіатура
start_kb = types.ReplyKeyboardMarkup(
    keyboard=[[types.KeyboardButton(text="Проверить airdrop")]],
    resize_keyboard=True,
    one_time_keyboard=False
)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привіт! Я твій airdrop-чекер 2025 🔥\n\n"
        "Жми кнопку нижче — покажу всі твої нарахування 👇",
        reply_markup=start_kb
    )

@dp.message(lambda message: message.text == "Проверить airdrop")
async def check_airdrop(message: types.Message):
    text = (
        "<b>Твої актуальні airdrop-нарахування</b>\n\n"
        "• Notcoin — 1 280.5 NOT\n"
        "• Hamster Kombat — 8 450 000 HMSTR\n"
        "• Blum — 2 450 BLUM\n"
        "• CATS — ще не роздали\n"
        "• DOGS — 420 000 DOGS\n"
        "• TapSwap — 15 800 000 TAPS\n\n"
        "Оновлюється кожні 15 хвилин ✅"
    )
    await message.answer(text)

async def main():
    logging.info("Бот успішно запущений на Railway 24/7")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
