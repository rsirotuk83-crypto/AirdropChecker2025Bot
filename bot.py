import os
import asyncio
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram import F

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

PAYMENT_LINK = "https://t.me/send?start=IVWQeJXKYVsd"   # ← свій платіжний лінк

# Мови
TEXTS = {
    "uk": {"start": "Привіт! @CryptoComboDaily — всі комбо та коди в одному місці\n\nОбери мову:",
           "set": "Мову змінено на українську 🇺🇦"},
    "ru": {"start": "Привет! @CryptoComboDaily — все комбо и коды в одном месте\n\nВыбери язык:",
           "set": "Язык изменён на русский 🇷🇺"},
    "en": {"start": "Hey! @CryptoComboDaily — all combos & codes in one place\n\nChoose language:",
           "set": "Language set to English 🇬🇧"}
}

def load_lang():
    if os.path.exists("lang.json"):
        with open("lang.json") as f:
            return json.load(f)
    return {}

def save_lang(data):
    with open("lang.json", "w") as f:
        json.dump(data, f)

langs = load_lang()

# Кнопки (БЕЗ емодзі в тексті — це важливо!)
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="English", callback_data="lang_en")],
    [types.InlineKeyboardButton(text="Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton(text="Українська", callback_data="lang_uk")]
])

main_kb = types.ReplyKeyboardMarkup(keyboard=[
    [types.KeyboardButton(text="Сьогоднішні комбо")]
], resize_keyboard=True)

@dp.message(Command("start"))
async def start(msg: types.Message):
    user_id = str(msg.from_user.id)
    lang = langs.get(user_id, "en")
    await msg.answer(TEXTS[lang]["start"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def change_lang(cb: types.CallbackQuery):
    lang = cb.data.split("_")[1]
    user_id = str(cb.from_user.id)
    langs[user_id] = lang
    save_lang(langs)
    await cb.message.edit_text(TEXTS[lang]["set"], reply_markup=main_kb)
    await cb.answer()

@dp.message(F.text == "Сьогоднішні комбо")
async def combos(msg: types.Message):
    date = datetime.now().strftime("%d.%m.%Y")
    text = f"<b>Комбо та коди на {date}</b>\n\n".format(date)
    text += ("Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
             "Blum → Cipher: FREEDOM\n"
             "Notcoin → Morse: · − · · − ·\n"
             "TapSwap → Cinema: MATRIX\n"
             "CATS → Launch code: MEOW2025\n"
             "PixelTap → ⚔️➜🛡️➜\n"
             "Rocky Rabbit → 3→1→4→2\n"
             "Yescoin → ←↑→↓←\n"
             "DOGS → DOGS2025\n"
             "+ ще 10 ігор щодня…")

    # Преміум
    paid = False
    if os.path.exists("paid.txt"):
        with open("paid.txt") as f:
            if str(msg.from_user.id) in f.read():
                paid = True

    if not paid:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Преміум 1$", url=PAYMENT_LINK)],
            [types.InlineKeyboardButton(text="Я оплатив", callback_data="paid")]
        ])
        text += "\n\n<b>Преміум 1$</b> — ранній доступ + приватні сигнали"
        await msg.answer(text, reply_markup=kb)
    else:
        await msg.answer(text, reply_markup=main_kb)

@dp.callback_query(F.data == "paid")
async def paid(cb: types.CallbackQuery):
    with open("paid.txt", "a") as f:
        f.write(f"{cb.from_user.id}\n")
    await cb.message.edit_text("Преміум активовано назавжди!")
    await cb.answer()

async def main():
    print("БОТ ЖИВИЙ!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
