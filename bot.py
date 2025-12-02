import os
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Твоє платіжне посилання (заміни, якщо треба)
PAYMENT_LINK = "https://t.me/send?start=IVWQeJXKYVsd"

# Файли для збереження
LANG_FILE = "user_lang.json"
PAID_FILE = "paid_users.txt"

# === ТЕКСТИ ===
TEXTS = {
    "uk": {
        "start": "🚀 Привіт! @CryptoComboDaily — всі щоденні комбо, шифри та коди 20+ тапалок в одному місці\n\nОбери мову:",
        "today": "🔥 <b>Комбо та коди на {date}</b>\n\n",
        "combo": "🐹 Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
                 "🌸 Blum → Cipher: FREEDOM\n"
                 "🪙 Notcoin → Morse: · − · · − ·\n"
                 "🔄 TapSwap → Cinema: MATRIX\n"
                 "🐱 CATS → Launch code: MEOW2025\n"
                 "⚔️ PixelTap → ⚔️ ➜ 🛡️ ➜ 🔥\n"
                 "🐰 Rocky Rabbit → 3→1→4→2\n"
                 "💛 Yescoin → ←↑→↓←\n"
                 "🐶 DOGS → DOGS2025\n"
                 "+ ще 12 ігор щодня...",
        "premium": "\n💎 <b>Преміум 1$</b> — ранній доступ за 30 хв + приватні сигнали",
        "paid": "🎉 Вітаю! Преміум активовано назавжди!",
        "lang_set": "🇺🇦 Мову змінено на українську"
    },
    "ru": {
        "start": "🚀 Привет! @CryptoComboDaily — все комбо, шифры и коды 20+ тапалок в одном месте\n\nВыбери язык:",
        "today": "🔥 <b>Комбо и коды на {date}</b>\n\n",
        "combo": "🐹 Hamster Kombat → Пицца ➜ Кошелёк ➜ Ракета\n"
                 "🌸 Blum → Cipher: СВОБОДА\n"
                 "🪙 Notcoin → Морзе: · − · · − ·\n"
                 "🔄 TapSwap → Cinema: МАТРИЦА\n"
                 "🐱 CATS → Launch code: МЯУ2025\n"
                 "⚔️ PixelTap → ⚔️ ➜ 🛡️ ➜ 🔥\n"
                 "🐰 Rocky Rabbit → 3→1→4→2\n"
                 "💛 Yescoin → ←↑→↓←\n"
                 "🐶 DOGS → DOGS2025\n"
                 "+ ещё 12 игр каждый день...",
        "premium": "\n💎 <b>Премиум 1$</b> — ранний доступ + приватные сигналы",
        "paid": "🎉 Поздравляю! Премиум активирован навсегда!",
        "lang_set": "🇷🇺 Язык изменён на русский"
    },
    "en": {
        "start": "🚀 Hey! @CryptoComboDaily — all daily combos, ciphers & codes 20+ tap-games in one place\n\nChoose language:",
        "today": "🔥 <b>Today’s combos & codes — {date}</b>\n\n",
        "combo": "🐹 Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
                 "🌸 Blum → Cipher: FREEDOM\n"
                 "🪙 Notcoin → Morse: · − · · − ·\n"
                 "🔄 TapSwap → Cinema: MATRIX\n"
                 "🐱 CATS → Launch code: MEOW2025\n"
                 "⚔️ PixelTap → ⚔️ ➜ 🛡️ ➜ 🔥\n"
                 "🐰 Rocky Rabbit → 3→1→4→2\n"
                 "💛 Yescoin → ←↑→↓←\n"
                 "🐶 DOGS → DOGS2025\n"
                 "+ 12 more games every day...",
        "premium": "\n💎 <b>Premium $1</b> — early access 30 min + private signals",
        "paid": "🎉 Congrats! Premium activated forever!",
        "lang_set": "🇬🇧 Language set to English"
    }
}

def get_lang(user_id):
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE) as f:
                data = eval(f.read())
            return data.get(str(user_id), "en")
        except:
            pass
    return "en"

def save_lang(user_id, lang):
    data = {}
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE) as f:
                data = eval(f.read())
        except:
            pass
    data = {}
    data[str(user_id)] = lang
    with open(LANG_FILE, "w") as f:
        f.write(str(data))

# Клавіатури
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
    [types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")]
])

main_kb = types.ReplyKeyboardMarkup(keyboard=[
    [types.KeyboardButton(text="🔥 Сьогоднішні комбо / Today combos")]
], resize_keyboard=True)

premium_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton("💎 Преміум 1$", url=PAYMENT_LINK)],
    [types.InlineKeyboardButton("Я оплатив", callback_data="paid")]
])

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(TEXTS[get_lang(message.from_user.id)]["start"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    save_lang(callback.from_user.id, lang)
    await callback.message.edit_text(TEXTS[lang]["lang_set"], reply_markup=main_kb)
    await callback.answer()

@dp.message(F.text.lower().contains("комбо") | F.text.lower().contains("combo"))
async def combos(message: types.Message):
    lang = get_lang(message.from_user.id)
    date_str = datetime.now().strftime("%d.%m.%Y")
    text = TEXTS[lang]["today"].format(date=date_str) + TEXTS[lang]["combo"]
    
    user_id = str(message.from_user.id)
    paid_users = []
    if os.path.exists(PAID_FILE):
        with open(PAID_FILE) as f:
            paid_users = f.read().splitlines()
    
    if user_id not in paid_users:
        text += TEXTS[lang]["premium"]
        await message.answer(text, reply_markup=premium_kb)
    else:
        await message.answer(text, reply_markup=main_kb)

@dp.callback_query(F.data == "paid")
async def paid(callback: types.CallbackQuery):
    with open(PAID_FILE, "a") as f:
        f.write(f"{callback.from_user.id}\n")
    lang = get_lang(callback.from_user.id)
    await callback.message.edit_text(TEXTS[lang]["paid"], reply_markup=main_kb)
    await callback.answer("✅")

async def main():
    logging.info("@CryptoComboDaily запущено!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
