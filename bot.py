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

# Твоє платіжне посилання
PAYMENT_LINK = "https://t.me/send?start=IVWQeJXKYVsd"

# Зберігання мови користувача
USER_LANG_FILE = "user_lang.json"

def load_langs():
    if os.path.exists(USER_LANG_FILE):
        with open(USER_LANG_FILE) as f:
            return eval(f.read())
    return {}

def save_langs(data):
    with open(USER_LANG_FILE, "w") as f:
        f.write(str(data))

LANGS = load_langs()

# === ТЕКСТИ НА ТРЬОХ МОВАХ ===
TEXTS = {
    "uk": {
        "start": "Привіт! @CryptoComboDaily — всі комбо, шифри та коди в одному місці\n\n"
                 "Щодня оновлюється о 00:05 та 12:05\n"
                 "Обери мову 🇺🇦",
        "today": "<b>Комбо та коди на сьогодні — {date}</b>\n\n",
        "combo": "Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
                 "Blum → Cipher: FREEDOM\n"
                 "Notcoin → Morse: · − · · − ·\n"
                 "TapSwap → Cinema: MATRIX\n"
                 "CATS → Launch code: CAT2025\n"
                 "PixelTap → ⚔️ ➜ 🛡️ ➜ 🔥\n"
                 "Rocky Rabbit → 3→1→4→2\n"
                 "Yescoin → ←↑→↓←\n"
                 "+ ще 15 ігор...",
        "premium": "\n\nПреміум 1$ — ранній доступ + приватні сигнали",
        "paid": "Вітаю! Преміум активовано назавжди!",
        "lang_set": "Мову змінено на українську 🇺🇦"
    },
    "ru": {
        "start": "Привет! @CryptoComboDaily — все комбо, шифры и коды в одном месте\n\n"
                 "Обновляется каждый день в 00:05 и 12:05\n"
                 "Выбери язык 🇷🇺",
        "today": "<b>Комбо и коды на сегодня — {date}</b>\n\n",
        "combo": "Hamster Kombat → Пицца ➜ Кошелёк ➜ Ракета\n"
                 "Blum → Cipher: СВОБОДА\n"
                 "Notcoin → Морзе: · − · · − ·\n"
                 "TapSwap → Cinema: МАТРИЦА\n"
                 "CATS → Launch code: МЯУ2025\n"
                 "PixelTap → ⚔️ ➜ 🛡️ ➜ 🔥\n"
                 "Rocky Rabbit → 3→1→4→2\n"
                 "Yescoin → ←↑→↓←\n"
                 "+ ещё 15 игр...",
        "premium": "\n\nПремиум 1$ — ранний доступ + приватные сигналы",
        "paid": "Поздравляю! Премиум активирован навсегда!",
        "lang_set": "Язык изменён на русский 🇷🇺"
    },
    "en": {
        "start": "Hey! @CryptoComboDaily — all combos, ciphers & codes in one place\n\n"
                 "Updated daily at 00:05 & 12:05\n"
                 "Choose language 🇬🇧",
        "today": "<b>Today’s combos & codes — {date}</b>\n\n",
        "combo": "Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
                 "Blum → Cipher: FREEDOM\n"
                 "Notcoin → Morse: · − · · − ·\n"
                 "TapSwap → Cinema: MATRIX\n"
                 "CATS → Launch code: MEOW2025\n"
                 "PixelTap → ⚔️ ➜ 🛡️ ➜ 🔥\n"
                 "Rocky Rabbit → 3→1→4→2\n"
                 "Yescoin → ←↑→↓←\n"
                 "+ 15 more games...",
        "premium": "\n\nPremium $1 — early access + private signals",
        "paid": "Congrats! Premium activated forever!",
        "lang_set": "Language set to English 🇬🇧"
    }
}

def get_lang(user_id):
    return LANGS.get(str(user_id), "en")

# Клавіатури
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
    [types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_uk")]
])

main_kb = types.ReplyKeyboardMarkup(keyboard=[
    [types.KeyboardButton(text="Сьогоднішні комбо / Today combos / Комбо сегодня")]
], resize_keyboard=True)

premium_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton("Преміум 1$ / Premium $1", url=PAYMENT_LINK)],
    [types.InlineKeyboardButton("Я оплатив / I paid", callback_data="paid")]
])

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(TEXTS[get_lang(message.from_user.id)]["start"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    LANGS[str(callback.from_user.id)] = lang
    save_langs(LANGS)
    await callback.message.edit_text(TEXTS[lang]["lang_set"], reply_markup=main_kb)
    await callback.answer()

@dp.message(F.text.contains("комбо") | F.text.contains("combo") | F.text.contains("Комбо"))
async def today_combos(message: types.Message):
    lang = get_lang(message.from_user.id)
    date_str = datetime.now().strftime("%d.%m.%Y")
    text = TEXTS[lang]["today"].format(date=date_str) + TEXTS[lang]["combo"]
    if str(message.from_user.id) not in open("paid_users.txt").read():
        text += TEXTS[lang]["premium"]
        await message.answer(text, reply_markup=premium_kb)
    else:
        await message.answer(text, reply_markup=main_kb)

@dp.callback_query(F.data == "paid")
async def paid(callback: types.CallbackQuery):
    with open("paid_users.txt", "a") as f:
        f.write(f"{callback.from_user.id}\n")
    lang = get_lang(callback.from_user.id)
    await callback.message.edit_text(TEXTS[lang]["paid"], reply_markup=main_kb)
    await callback.answer("✅")

async def main():
    logging.info("@CryptoComboDaily запущено з 3 мовами!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
