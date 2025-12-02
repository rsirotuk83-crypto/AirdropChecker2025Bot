import os
import logging
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# ←←← ТУТ ТИ МІНЯЄШ ЦИФРИ, КОЛИ ТРЕБА
CHECK_DATA = """
<b>Твої airdrop-нарахування (02.12.2025)</b>

• Notcoin → 1 280.5 NOT
• Hamster Kombat → 8 450 000 HMSTR
• Blum → 2 450 BLUM
• CATS → ще не роздали
• DOGS → 420 000 DOGS
• TapSwap → 15 800 000 TAPS
• Pixels → 280 000 PIXEL

Оновлюється кожні 15 хвилин
"""

# Клавіатура
kb = types.ReplyKeyboardMarkup(
    keyboard=[[types.KeyboardButton(text="Проверить airdrop")]],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привіт! Я твій airdrop-чекер 2025\n\n"
        "Натискай кнопку нижче — покажу всі твої нарахування 👇",
        reply_markup=kb
    )

@dp.message(lambda m: m.text == "Проверить airdrop")
async def check(message: types.Message):
    await message.answer(CHECK_DATA, reply_markup=kb)

async def main():
    logging.info("AirdropChecker2025Bot успішно запущений!")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
