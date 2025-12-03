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

LANG_FILE = "lang.json"
PAID_FILE = "paid.txt"

# ТЕКСТИ НА ВСІХ МОВАХ (повністю)
TEXTS = {
    "uk": {
        "welcome": "Привіт! @CryptoComboDaily\nВсі комбо та коди 20+ тапалок в одному місці\n\nОбери мову:",
        "lang_set": "Мову змінено на українську",
        "btn_combo": "Сьогоднішні комбо"
    },
    "ru": {
        "welcome": "Привет! @CryptoComboDaily\nВсе комбо и коды 20+ тапалок в одном месте\n\nВыбери язык:",
        "lang_set": "Язык изменён на русский",
        "btn_combo": "Сегодняшние комбо"
    },
    "en": {
        "welcome": "Hey! @CryptoComboDaily\nAll combos & codes for 20+ tap-games in one place\n\nChoose language:",
        "lang_set": "Language set to English",
        "btn_combo": "Today's combos"
    },
    "es": {
        "welcome": "¡Hola! @CryptoComboDaily\nTodos los combos y códigos de 20+ tap-games en un solo lugar\n\nElige idioma:",
        "lang_set": "Idioma cambiado a español",
        "btn_combo": "Combos de hoy"
    },
    "de": {
        "welcome": "Hallo! @CryptoComboDaily\nAlle Combos & Codes von 20+ Tap-Games an einem Ort\n\nSprache wählen:",
        "lang_set": "Sprache auf Deutsch geändert",
        "btn_combo": "Heutige Combos"
    }
}

def get_lang(user_id):
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(str(user_id), "uk")
        except:
            return "uk"
    return "uk"

def save_lang(user_id, lang):
    data = {}
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
    data[str(user_id)] = lang
    with open(LANG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

# Клавіатура вибору мови
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="Українська", callback_data="lang_uk")],
    [types.InlineKeyboardButton(text="Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton(text="English", callback_data="lang_en")],
    [types.InlineKeyboardButton(text="Español", callback_data="lang_es")],
    [types.InlineKeyboardButton(text="Deutsch", callback_data="lang_de")]
])

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(TEXTS["uk"]["welcome"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    save_lang(callback.from_user.id, lang)
    
    # Показуємо повідомлення правильною мовою + головна кнопка
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text=TEXTS[lang]["btn_combo"])]
    ], resize_keyboard=True)
    
    await callback.message.edit_text(TEXTS[lang]["lang_set"], reply_markup=kb)
    await callback.answer()

@dp.message(F.text.in_(["Сьогоднішні комбо", "Сегодняшние комбо", "Today's combos", "Combos de hoy", "Heutige Combos"]))
async def combos(message: types.Message):
    lang = get_lang(message.from_user.id)
    text = f"<b>Комбо на {datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
    text += ("Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\nBlum → FREEDOM\nTapSwap → MATRIX\nCATS → MEOW2025\nRocky Rabbit → 3→1→4→2\n+ ще 15 ігор…")
    
    paid = False
    if os.path.exists(PAID_FILE):
        with open(PAID_FILE) as f:
            paid = str(message.from_user.id) in f.read().splitlines()
    
    if not paid:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Преміум 1$", url="https://t.me/send?start=IVWQeJXKYVsd")],
            [types.InlineKeyboardButton(text="Я оплатив", callback_data="paid")]
        ])
        text += "\n\n<b>Преміум 1$</b> — ранній доступ"
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(text)

@dp.callback_query(F.data == "paid")
async def paid(callback: types.CallbackQuery):
    with open(PAID_FILE, "a") as f:
        f.write(f"{callback.from_user.id}\n")
    await callback.message.edit_text("Преміум активовано!")

async def main():
    print("БОТ ЖИВИЙ — ВСІ МОВИ ПРАЦЮЮТЬ!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
