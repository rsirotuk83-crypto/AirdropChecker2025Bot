import os
import asyncio
import json
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
from aiogram import F

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()

PAYMENT_LINK = "https://t.me/send?start=IVWQeJXKYVsd"  # ← твій платіжний

# ——— Мови ———
TEXTS = {
    "uk": {
        "start": "Привіт! @CryptoComboDaily — всі комбо та коди в одному місці\n\nОбери мову:",
        "set": "Мову змінено на українську",
        "btn": "Сьогоднішні комбо"
    },
    "ru": {
        "start": "Привет! @CryptoComboDaily — все комбо и коды в одном месте\n\nВыбери язык:",
        "set": "Язык изменён на русский",
        "btn": "Сьогоднішні комбо"
    },
    "en": {
        "start": "Hey! @CryptoComboDaily — all combos & codes in one place\n\nChoose language:",
        "set": "Language set to English",
        "btn": "Today combos"
    }
}

# ——— Файли ———
def get_langs():
    if os.path.exists("lang.json"):
        with open("lang.json") as f:
            return json.load(f)
    return {}

def save_langs(data):
    with open("lang.json", "w") as f:
        json.dump(data, f)

langs = get_langs()

# ——— Клавіатури ———
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="English", callback_data="lang_en")],
    [types.InlineKeyboardButton(text="Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton(text="Українська", callback_data="lang_uk")]
])

def get_main_kb(lang_code):
    return types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text=TEXTS[lang_code]["btn"])]
    ], resize_keyboard=True)

# ——— Хендлери ———
@dp.message(CommandStart())
async def start(message: types.Message):
    uid = str(message.from_user.id)
    lang = langs.get(uid, "en")
    await message.answer(TEXTS[lang]["start"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    langs[str(callback.from_user.id)] = lang
    save_langs(langs)
    await callback.message.edit_text(TEXTS[lang]["set"], reply_markup=get_main_kb(lang))
    await callback.answer()

@dp.message(F.text.regexp(r"(?i)комбо|combo"))
async def send_combos(message: types.Message):
    uid = str(message.from_user.id)
    lang = langs.get(uid, "en")
    date = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%d.%m.%Y")  # Київський час

    text = f"<b>Комбо та коди на {date}</b>\n\n"
    text += ("Hamster Kombat — Pizza ➜ Wallet ➜ Rocket\n"
              "Blum — Cipher: FREEDOM\n"
              "Notcoin — Морзе: · − · · − ·\n"
              "TapSwap — Cinema: MATRIX\n"
              "CATS — Launch: MEOW2025\n"
              "PixelTap — ⚔️➜🛡️➜Fire\n"
              "Rocky Rabbit — 3→1→4→2\n"
              "Yescoin — ←↑→↓←\n"
              "DOGS — DOGS2025\n"
              "+ ще 12 ігор щодня…")

    # Преміум
    paid = False
    if os.path.exists("paid.txt"):
        with open("paid.txt") as f:
            if uid in f.read():
                paid = True

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Преміум 1$", url=PAYMENT_LINK)],
        [types.InlineKeyboardButton(text="Я оплатив", callback_data="paid")]
    ]) if not paid else get_main_kb(lang)

    if not paid:
        text += "\n\n<b>Преміум 1$</b> — ранній доступ + приватні сигнали"

    await message.answer(text, reply_markup=kb, disable_web_page_preview=True)

@dp.callback_query(F.data == "paid")
async def activate(callback: types.CallbackQuery):
    with open("paid.txt", "a") as f:
        f.write(f"{callback.from_user.id}\n")
    await callback.message.edit_text("Преміум активовано назавжди!")
    await callback.answer()

async def main():
    print("Бот @CryptoComboDaily запущено і працює!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
