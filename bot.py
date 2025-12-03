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

# === ФАЙЛИ ===
LANG_FILE = "lang.json"
PAID_FILE = "paid.txt"

# === ПОВНІ ПЕРЕКЛАДИ НА 5 МОВ ===
TEXTS = {
    "uk": {
        "start": "Привіт! @CryptoComboDaily\nВсі комбо та коди 20+ тапалок в одному місці\n\nОбери мову:",
        "lang_set": "Мову змінено на українську ✅",
        "combo_btn": "Сьогоднішні комбо",
        "premium": "Преміум 1$",
        "paid_text": "Я оплатив"
    },
    "ru": {
        "start": "Привет! @CryptoComboDaily\nВсе комбо и коды 20+ тапалок в одном месте\n\nВыбери язык:",
        "lang_set": "Язык изменён на русский ✅",
        "combo_btn": "Сегодняшние комбо",
        "premium": "Премиум 1$",
        "paid_text": "Я оплатил"
    },
    "en": {
        "start": "Hey! @CryptoComboDaily\nAll combos & codes for 20+ tap games\n\nChoose language:",
        "lang_set": "Language set to English ✅",
        "combo_btn": "Today's combos",
        "premium": "Premium $1",
        "paid_text": "I paid"
    },
    "es": {
        "start": "¡Hola! @CryptoComboDaily\nTodos los combos y códigos de 20+ tap games\n\nElige idioma:",
        "lang_set": "Idioma cambiado a español ✅",
        "combo_btn": "Combos de hoy",
        "premium": "Premium 1$",
        "paid_text": "Ya pagué"
    },
    "de": {
        "start": "Hallo! @CryptoComboDaily\nAlle Combos & Codes von 20+ Tap-Games\n\nSprache wählen:",
        "lang_set": "Sprache auf Deutsch geändert ✅",
        "combo_btn": "Heutige Combos",
        "premium": "Premium 1$",
        "paid_text": "Ich habe bezahlt"
    }
}

def get_user_lang(user_id):
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(str(user_id), "uk")
        except:
            return "uk"
    return "uk"

def save_user_lang(user_id, lang):
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

# === КНОПКИ ===
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton("Українська", callback_data="lang_uk")],
    [types.InlineKeyboardButton("Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton("English", callback_data="lang_en")],
    [types.InlineKeyboardButton("Español", callback_data="lang_es")],
    [types.InlineKeyboardButton("Deutsch", callback_data="lang_de")]
])

@dp.message(CommandStart())
async def start(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    await message.answer(TEXTS[lang]["start"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def change_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    save_user_lang(callback.from_user.id, lang)
    
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text=TEXTS[lang]["combo_btn"])]
    ], resize_keyboard=True)
    
    await callback.message.edit_text(TEXTS[lang]["lang_set"], reply_markup=kb)
    await callback.answer()

@dp.message(F.text.func(lambda text: any(text == TEXTS[lang]["combo_btn"] for lang in TEXTS)))
async def send_combos(message: types.Message):
    lang = get_user_lang(message.from_user.id)
    
    combos = ("Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
              "Blum → Cipher: FREEDOM\n"
              "TapSwap → MATRIX\n"
              "CATS → MEOW2025\n"
              "Rocky Rabbit → 3→1→4→2\n"
              "Yescoin → ←↑→↓←\n"
              "DOGS → DOGS2025\n"
              "+ ще 15 ігор…")
    
    text = f"<b>Комбо на {datetime.now().strftime('%d.%m.%Y')}</b>\n\n{combos}"
    
    paid = False
    if os.path.exists(PAID_FILE):
        with open(PAID_FILE, "r") as f:
            paid
