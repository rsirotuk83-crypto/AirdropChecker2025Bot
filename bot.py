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

# Простий файл для збереження мови (всі по дефолту українська)
LANG_FILE = "lang.json"
PAID_FILE = "paid.txt"

def get_lang(user_id):
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE) as f:
                data = json.load(f)
                return data.get(str(user_id), "uk")
        except:
            return "uk"
    return "uk"

def save_lang(user_id, lang):
    data = {}
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE) as f:
                data = json.load(f)
        except:
            pass
    data[str(user_id)] = lang
    with open(LANG_FILE, "w") as f:
        json.dump(data, f)

# Клавіатури
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="Українська", callback_data="lang_uk")],
    [types.InlineKeyboardButton(text="Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton(text="English", callback_data="lang_en")]
])

main_kb = types.ReplyKeyboardMarkup(keyboard=[
    [types.KeyboardButton(text="Сьогоднішні комбо 🔥")]
], resize_keyboard=True)

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Привіт! @CryptoComboDaily\nВсі комбо та коди 20+ тапалок в одному місці\n\nОбери мову:",
        reply_markup=lang_kb
    )

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    save_lang(callback.from_user.id, lang)
    await callback.message.edit_text("Мову встановлено ✅", reply_markup=main_kb)
    await callback.answer()

@dp.message(F.text == "Сьогоднішні комбо 🔥")
async def combos(message: types.Message):
    text = f"<b>Комбо та коди на {datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
    text += ("Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
             "Blum → Cipher: FREEDOM\n"
             "Notcoin → · − · · − ·\n"
             "TapSwap → MATRIX\n"
             "CATS → MEOW2025\n"
             "PixelTap → ⚔️ ➜ 🛡️ ➜ 🔥\n"
             "Rocky Rabbit → 3→1→4→2\n"
             "Yescoin → ←↑→↓←\n"
             "DOGS → DOGS2025\n"
             "+ ще 12 ігор щодня…")

    # Преміум
    paid = False
    if os.path.exists(PAID_FILE):
        with open(PAID_FILE) as f:
            paid = str(message.from_user.id) in f.read()

    if not paid:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Преміум 1$", url="https://t.me/send?start=IVWQ
