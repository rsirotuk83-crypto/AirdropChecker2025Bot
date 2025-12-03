import os
import asyncio
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram import F

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ← ТУТ ТВІЙ ПЛАТІЖНИЙ ЛІНК
PAYMENT_LINK = "https://t.me/send?start=IVWQeJXKYVsd"

# Мови
TEXTS = {
    "uk": {"start": "Привіт! @CryptoComboDaily — всі комбо та коди в одному місці\n\nОбери мову:", "set": "Мову змінено на українську"},
    "ru": {"start": "Привет! @CryptoComboDaily — все комбо и коды в одном месте\n\nВыбери язык:", "set": "Язык изменён на русский"},
    "en": {"start": "Hey! @CryptoComboDaily — all combos & codes in one place\n\nChoose language:", "set": "Language set to English"}
}

# Завантаження/збереження мов
def load_langs():
    if os.path.exists("lang.json"):
        with open("lang.json") as f:
            return json.load(f)
    return {}

def save_langs(data):
    with open("lang.json", "w") as f:
        json.dump(data, f)

langs = load_langs()

# Кнопки
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="English", callback_data="setlang_en")],
    [types.InlineKeyboardButton(text="Русский", callback_data="setlang_ru")],
    [types.InlineKeyboardButton(text="Українська", callback_data="setlang_uk")]
])

main_kb = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="Сьогоднішні комбо")]], resize_keyboard=True)

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    lang = langs.get(user_id, "en")
    await message.answer(TEXTS[lang]["start"], reply_markup=lang_kb)

# ВАЖЛИВО: змінив callback_data на "setlang_" — тепер 100% спрацьовує
@dp.callback_query(F.data.startswith("setlang_"))
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    langs[str(callback.from_user.id)] = lang
    save_langs(langs)
    await callback.message.edit_text(TEXTS[lang]["set"], reply_markup=main_kb)
    await callback.answer("Готово!")

@dp.message(F.text == "Сьогоднішні комбо")
async def combos
