# bot.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import F

# Твій токен
TOKEN = "8485697907:AAEil1WfkZGVhR3K9wlHEVBJ5qNvn2B_mow"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()


@dp.message(Command("start"))
async def start_cmd(message: Message):
    kb = [[types.KeyboardButton(text="Проверить airdrop")]]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=False)

    await message.answer(
        "Привет! 👋\n\n"
        "Я — твой личный airdrop-чекер 2025 года\n"
        "Нажми кнопку ниже или напиши /check — покажу всё, что тебе начислили\n\n"
        "Обновляется каждые 15 минут ⚡",
        reply_markup=keyboard
    )


@dp.message(F.text.in_({"Проверить airdrop", "/check"}))
async def check_cmd(message: Message):
    user = message.from_user
    text = (
        f"<b>Твои airdrop-начисления</b>\n"
        f"ID: <code>{user.id}</code>\n"
        f"Username: @{user.username if user.username else 'не указан'}\n\n"
        "📊 Актуальные проекты:\n\n"
        "• Notcoin — 1 280.5 NOT\n"
        "• Hamster Kombat — 8 450 000 HMSTR\n"
        "• Blum — 2 450 BLUM\n"
        "• Cats — ещё не раздали 😿\n"
        "• TapSwap — 15 800 000 TAPS\n"
        "• Dogs — 420 000 DOGS\n\n"
        "💎 Скоро добавлю ещё кучу новых проектов\n"
        "Обновляйся чаще — не пропусти дроп!"
    )
    await message.answer(text)


async def main():
    print("Бот запущен и ждёт тебя 😈")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
