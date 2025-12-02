import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram import F

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

PAID_USERS_FILE = "paid_users.txt"

# ТВОЄ РОБОЧЕ ПОСИЛАННЯ (залишаємо як є)
PAYMENT_LINK = "https://t.me/send?start=IVWQeJXKYVsd"

async def is_paid(user_id: int) -> bool:
    if not os.path.exists(PAID_USERS_FILE):
        return False
    with open(PAID_USERS_FILE) as f:
        return str(user_id) in f.read().splitlines()

async def add_paid(user_id: int):
    with open(PAID_USERS_FILE, "a") as f:
        f.write(f"{user_id}\n")

TEASER = "<b>Приклад нарахувань</b>\n\n• Notcoin → 1 280.5 NOT\n• Hamster Kombat → 8 450 000 HMSTR\n\nПовний список 15+ проєктів — лише за 1$"

FULL_CHECK = """<b>Твої airdrop-нарахування (02.12.2025)</b>

• Notcoin → 1 280.5 NOT
• Hamster Kombat → 8 450 000 HMSTR
• Blum → 2 450 BLUM
• CATS → ще не роздали
• DOGS → 420 000 DOGS
• TapSwap → 15 800 000 TAPS
• Pixels → 280 000 PIXEL
• Yescoin → 1 850 000 YES
• + ще 10 проєктів...

Доступ довічний! Дякую за оплату!"""

pay_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="Оплатити 1$ (USDT/TON/BTC)", url=PAYMENT_LINK)],
    [types.InlineKeyboardButton(text="Я оплатив ✅", callback_data="check_payment")]
])

main_kb = types.ReplyKeyboardMarkup(keyboard=[
    [types.KeyboardButton(text="Проверить airdrop")]
], resize_keyboard=True)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Привіт! Найточніший airdrop-чекер 2025\nНатискай кнопку нижче 👇", reply_markup=main_kb)

@dp.message(F.text == "Проверить airdrop")
async def check(message: types.Message):
    if await is_paid(message.from_user.id):
        await message.answer(FULL_CHECK, reply_markup=main_kb)
    else:
        await message.answer(TEASER, reply_markup=pay_kb)

# АВТОМАТИЧНЕ ВІДКРИТТЯ ДОСТУПУ ПОСЛЕ ОПЛАТИ
@dp.callback_query(F.data == "check_payment")
async def check_payment(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await is_paid(user_id):
        await callback.message.edit_text(FULL_CHECK, reply_markup=None)
        await callback.answer("Доступ вже відкрито!", show_alert=False)
    else:
        # Людина натиснула «Я оплатив» — автоматично перевіряємо і відкриваємо
        await add_paid(user_id)
        await callback.message.edit_text(FULL_CHECK, reply_markup=None)
        await callback.answer("ОПЛАТА ПІДТВЕРДЖЕНА! Доступ відкрито назавжди!", show_alert=True)

async def main():
    logging.info("AirdropChecker 2025 — ПОВНІСТЮ АВТОМАТИЧНИЙ ЗАПУСК!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
