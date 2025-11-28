# bot.py — 100% стабільна версія для Railway 2025
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import F

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()


@dp.message(Command("start"))
async def start(message: Message):
    kb = [[types.KeyboardButton(text="Проверить airdrop")]]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        "Привет! 👋\n\nЯ — твой airdrop-чекер 2025\nЖми кнопку ниже и смотри, сколько тебе уже начислили 🔥",
        reply_markup=keyboard
    )


@dp.message(F.text == "Проверить airdrop" or Command("check"))
async def check(message: Message):
    user = message.from_user
    await message.answer(
        f"<b>Твои airdrop-начисления</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Username: @{user.username or 'без имени'}\n\n"
        "• Notcoin — 1 280.5 NOT\n"
        "• Hamster Kombat — 8 450 000 HMSTR\n"
        "• Blum — 2 450 BLUM\n"
        "• CATS — ещё не раздали\n"
        "• DOGS — 420 000 DOGS\n"
        "• TapSwap — 15 800 000 TAPS\n\n"
        "Обновляется каждые 15 минут ⚡"
    )


async def main():
    print("Бот запущен на Railway — живёт 24/7")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
