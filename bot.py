import os
import asyncio
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram import F

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Файли
LANG_FILE = "lang.json"
PAID_FILE = "paid.txt"

# === Клавіатури (додав іспанську і німецьку, як просив) ===
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="Українська", callback_data="lang_uk")],
    [types.InlineKeyboardButton(text="Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton(text="English", callback_data="lang_en")],
    [types.InlineKeyboardButton(text="Español", callback_data="lang_es")],
    [types.InlineKeyboardButton(text="Deutsch", callback_data="lang_de")]
])

main_kb = types.ReplyKeyboardMarkup(keyboard=[
    [types.KeyboardButton(text="Сьогоднішні комбо")]
], resize_keyboard=True, one_time_keyboard=False)

# === Старт ===
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Привіт! @CryptoComboDaily\n"
        "Всі комбо та коди 20+ тапалок в одному місці\n\n"
        "Обери мову:",
        reply_markup=lang_kb
    )

# === Вибір мови ===
@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    # Зберігаємо мову
    data = {}
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
    data[str(callback.from_user.id)] = lang
    with open(LANG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

    await callback.message.edit_text("Мову змінено!", reply_markup=main_kb)
    await callback.answer("Готово!")

# === Комбо ===
@dp.message(F.text == "Сьогоднішні комбо")
async def combos(message: types.Message):
    text = f"<b>Комбо та коди на {datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
    text += ("Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
             "Blum → Cipher: FREEDOM\n"
             "TapSwap → MATRIX\n"
             "CATS → MEOW2025\n"
             "Rocky Rabbit → 3→1→4→2\n"
             "Yescoin → ←↑→↓←\n"
             "DOGS → DOGS2025\n"
             "PixelTap → ⚔️ ➜ 🛡️ ➜ Fire\n"
             "+ ще 15 ігор щодня…")

    # Преміум
    paid = False
    if os.path.exists(PAID_FILE):
        with open(PAID_FILE, "r", encoding="utf-8") as f:
            paid = str(message.from_user.id) in f.read()

    if not paid:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Преміум 1$ (ранній доступ)", url="https://t.me/send?start=IVWQeJXKYVsd")],
            [types.InlineKeyboardButton(text="Я оплатив", callback_data="paid")]
        ])
        text += "\n\n<b>Преміум 1$</b> — комбо за 30 хв до всіх"
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=main_kb)

# === Активація преміуму ===
@dp.callback_query(F.data == "paid")
async def paid(callback: types.CallbackQuery):
    with open(PAID_FILE, "a", encoding="utf-8") as f:
        f.write(f"{callback.from_user.id}\n")
    await callback.message.edit_text("Преміум активовано назавжди!")
    await callback.answer("Успіх!")

# === Запуск ===
async def main():
    print("БОТ @CryptoComboDaily — ЖИВИЙ 100%")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
