import os
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram import F
from aiogram.fsm.storage.memory import MemoryStorage
import json

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

PAYMENT_LINK = "https://t.me/send?start=IVWQeJXKYVsd"  # ← заміни на свій платіжний

TEXTS = {
    "uk": {"start": "Привіт! @CryptoComboDaily — всі комбо та коди в одному місці\n\nОбери мову:", "lang_set": "Мову змінено на українську"},
    "ru": {"start": "Привет! @CryptoComboDaily — все комбо и коды в одном месте\n\nВыбери язык:", "lang_set": "Язык изменён на русский"},
    "en": {"start": "Hey! @CryptoComboDaily — all combos & codes in one place\n\nChoose language:", "lang_set": "Language set to English"}
}

def get_lang(user_id):
    if os.path.exists("lang.json"):
        try:
            with open("lang.json") as f:
                data = json.load(f)
            return data.get(str(user_id), "en")
        except: pass
    return "en"

def save_lang(user_id, lang):
    data = {}
    if os.path.exists("lang.json"):
        try:
            with open("lang.json") as f:
                data = json.load(f)
        except: pass
    data[str(user_id)] = lang
    with open("lang.json", "w") as f:
        json.dump(data, f)

# КНОПКИ БЕЗ ЕМОДЗІ — ТЕПЕР 100% ПРАЦЮЄ
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="English", callback_data="lang_en")],
    [types.InlineKeyboardButton(text="Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton(text="Українська", callback_data="lang_uk")]
])

main_kb = types.ReplyKeyboardMarkup(keyboard=[
    [types.KeyboardButton(text="Сьогоднішні комбо / Today combos")]
], resize_keyboard=True)

@dp.message(Command("start"))
async def start(message: types.Message):
    lang = get_lang(message.from_user.id)
    await message.answer(TEXTS[lang]["start"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    save_lang(callback.from_user.id, lang)
    await callback.message.edit_text(TEXTS[lang]["lang_set"], reply_markup=main_kb)
    await callback.answer()

@dp.message(F.text.regexp_matches(r"(?i)комбо|combo|today"))
async def combos(message: types.Message):
    lang = get_lang(message.from_user.id)
    date = datetime.now().strftime("%d.%m.%Y")
    text = f"Комбо на <b>{date}</b>\n\n"
    text += "🐹 Hamster → Pizza ➜ Wallet ➜ Rocket\n🌸 Blum → FREEDOM\n🪙 Notcoin → · − · · − ·\n🔄 TapSwap → MATRIX\n🐱 CATS → MEOW2025\n⚔️ PixelTap → ⚔️➜🛡️➜🔥\n🐰 Rocky Rabbit → 3→1→4→2\n+ ще 12 ігор..."
    
    paid = False
    if os.path.exists("paid.txt"):
        with open("paid.txt") as f:
            paid = str(message.from_user.id) in f.read().splitlines()
    
    if not paid:
        premium_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Преміум 1$", url=PAYMENT_LINK)],
            [types.InlineKeyboardButton(text="Я оплатив", callback_data="check_paid")]
        ])
        text += "\n\n💎 Преміум 1$ — ранній доступ + приватні сигнали"
        await message.answer(text, reply_markup=premium_kb)
    else:
        await message.answer(text, reply_markup=main_kb)

@dp.callback_query(F.data == "check_paid")
async def check_paid(callback: types.CallbackQuery):
    with open("paid.txt", "a") as f:
        f.write(f"{callback.from_user.id}\n")
    await callback.message.edit_text("Преміум активовано назавжди!")
    await callback.answer("Готово!")

async def main():
    print("@CryptoComboDaily — ЖИВИЙ!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
