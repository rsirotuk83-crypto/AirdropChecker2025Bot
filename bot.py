import os
import asyncio
import json
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram import F

TOKEN = os.getenv("TOKEN")
# ПРАВИЛЬНИЙ СПОСІБ ДЛЯ НОВОГО aiogram
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

PAYMENT_LINK = "https://t.me/send?start=IVWQeJXKYVsd"  # ← твій платіжний лінк

# Мови
TEXTS = {
    "uk": {"start": "Привіт! @CryptoComboDaily — всі комбо та коди в одному місці\n\nОбери мову:", "set": "Мову змінено на українську", "btn": "Сьогоднішні комбо"},
    "ru": {"start": "Привет! @CryptoComboDaily — все комбо и коды в одном месте\n\nВыбери язык:", "set": "Язык изменён на русский", "btn": "Сьогоднішні комбо"},
    "en": {"start": "Hey! @CryptoComboDaily — all combos & codes in one place\n\nChoose language:", "set": "Language set to English", "btn": "Today combos"}
}

# lang.json
def load_lang():
    if os.path.exists("lang.json"):
        with open("lang.json") as f:
            return json.load(f)
    return {}

def save_lang(data):
    with open("lang.json", "w") as f:
        json.dump(data, f)

langs = load_lang()

# Клавіатури
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="English", callback_data="lang_en")],
    [types.InlineKeyboardButton(text="Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton(text="Українська", callback_data="lang_uk")]
])

def main_kb(lang):
    return types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=TEXTS[lang]["btn"])]], resize_keyboard=True)

@dp.message(CommandStart())
async def start(message: types.Message):
    uid = str(message.from_user.id)
    lang = langs.get(uid, "en")
    await message.answer(TEXTS[lang]["start"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    langs[str(callback.from_user.id)] = lang
    save_lang(langs)
    await callback.message.edit_text(TEXTS[lang]["set"], reply_markup=main_kb(lang))
    await callback.answer()

@dp.message(F.text.regexp(r"(?i)комбо|combo"))
async def combos(message: types.Message):
    uid = str(message.from_user.id)
    lang = langs.get(uid, "en")
    date = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%d.%m.%Y")

    text = f"<b>Комбо та коди на {date}</b>\n\n"
    text += ("Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
             "Blum → Cipher: FREEDOM\n"
             "Notcoin → · − · · − ·\n"
             "TapSwap → MATRIX\n"
             "CATS → MEOW2025\n"
             "PixelTap → ⚔️➜🛡️➜Fire\n"
             "Rocky Rabbit → 3→1→4→2\n"
             "Yescoin → ←↑→↓←\n"
             "DOGS → DOGS2025\n"
             "+ ще 12 ігор щодня…")

    paid = False
    if os.path.exists("paid.txt"):
        with open("paid.txt") as f:
            paid = uid in f.read()

    if not paid:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Преміум 1$", url=PAYMENT_LINK)],
            [types.InlineKeyboardButton(text="Я оплатив", callback_data="paid")]
        ])
        text += "\n\n<b>Преміум 1$</b> — ранній доступ + приватні сигнали"
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=main_kb(lang))

@dp.callback_query(F.data == "paid")
async def activate(callback: types.CallbackQuery):
    with open("paid.txt", "a") as f:
        f.write(f"{callback.from_user.id}\n")
    await callback.message.edit_text("Преміум активовано назавжди!")
    await callback.answer("Готово!")

async def main():
    print("БОТ ЖИВИЙ І ПРАЦЮЄ НА 100%!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
