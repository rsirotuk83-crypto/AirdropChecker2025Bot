import os
import asyncio
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

LANG_FILE = "lang.json"
PAID_FILE = "paid.txt"

# ─── ВСІ ПЕРЕКЛАДИ ─────────────────────────────────────
TEXTS = {
    "uk": {"start":"Привіт! @CryptoComboDaily\nВсі комбо та коди 20+ тапалок в одному місці\n\nОбери мову:",
           "set":"Мову змінено на українську ✅",
           "btn":"Сьогоднішні комбо"},
    "ru": {"start":"Привет! @CryptoComboDaily\nВсе комбо и коды 20+ тапалок в одном месте\n\nВыбери язык:",
           "set":"Язык изменён на русский ✅",
           "btn":"Сегодняшние комбо"},
    "en": {"start":"Hey! @CryptoComboDaily\nAll combos & codes for 20+ tap games\n\nChoose language:",
           "set":"Language set to English ✅",
           "btn":"Today's combos"},
    "},
    "es": {"start":"¡Hola! @CryptoComboDaily\nTodos los combos y códigos de 20+ tap games\n\nElige idioma:",
           "set":"Idioma cambiado a español ✅",
           "btn":"Combos de hoy"},
    "de": {"start":"Hallo! @CryptoComboDaily\nAlle Combos & Codes von 20+ Tap-Games\n\nSprache wählen:",
           "set":"Sprache auf Deutsch geändert ✅",
           "btn":"Heutige Combos"}
}

def get_lang(uid): 
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE) as f:
                return json.load(f).get(str(uid), "uk")
    return "uk"

def save_lang(uid, lang):
    data = {}
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE) as f:
                data = json.load(f)
        except: pass
    data[str(uid)] = lang
    with open(LANG_FILE, "w") as f:
        json.dump(data, f)

# ─── КНОПКИ ───────────────────────────────────────────
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton("Українська", callback_data="lang_uk")],
    [types.InlineKeyboardButton("Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton("English", callback_data="lang_en")],
    [types.InlineKeyboardButton("Español", callback_data="lang_es")],
    [types.InlineKeyboardButton("Deutsch", callback_data="lang_de")]
])

@dp.message(CommandStart())
async def start(msg: types.Message):
    l = get_lang(msg.from_user.id)
    await msg.answer(TEXTS[l]["start"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(cb: types.CallbackQuery):
    l = cb.data.split("_")[1]
    save_lang(cb.from_user.id, l)
    kb = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(TEXTS[l]["btn"])]], resize_keyboard=True)
    await cb.message.edit_text(TEXTS[l]["set"], reply_markup=kb)
    await cb.answer()

@dp.message(F.text.func(lambda m: m in [TEXTS[x]["btn"] for x in TEXTS]))
async def combos(msg: types.Message):
    l = get_lang(msg.from_user.id)
    text = f"<b>Комбо та коди на {datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
    text += ("Hamster → Pizza ➜ Wallet ➜ Rocket\nBlum → FREEDOM\nTapSwap → MATRIX\nCATS → MEOW2025\n"
              "Rocky Rabbit → 3→1→4→2\nYescoin → ←↑→↓←\nDOGS → DOGS2025\n+ ще 15 ігор…")

    paid = os.path.exists(PAID_FILE) and str(msg.from_user.id) in open(PAID_FILE).read()

    if not paid:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton("Преміум 1$", url="https://t.me/send?start=IVWQeJXKYVsd")],
            [types.InlineKeyboardButton("Я оплатив", callback_data="paid")]
        ])
        text += "\n\n<b>Преміум 1$</b> — ранній доступ"
        await msg.answer(text, reply_markup=kb)
    else:
        await msg.answer(text)

@dp.callback_query(F.data == "paid")
async def paid(cb: types.CallbackQuery):
    open(PAID_FILE, "a").write(f"{cb.from_user.id}\n")
    await cb.message.edit_text("Преміум активовано назавжди!")
    await cb.answer()

async def main():
    print("БОТ ЗАПУЩЕНО — ВСЕ ПРАЦЮЄ")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
