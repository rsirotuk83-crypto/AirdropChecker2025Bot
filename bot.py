import os
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram import F
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Твоє платіжне посилання
PAYMENT_LINK = "https://t.me/send?start=IVWQeJXKYVsd"

# === ТЕКСТИ ===
TEXTS = {
    "uk": {"start": "Привіт! @CryptoComboDaily — всі комбо та коди в одному місці\n\nОбери мову:",
           "today": "<b>Комбо на {date}</b>\n\n",
           "combo": "Hamster → Pizza ➜ Wallet ➜ Rocket\nBlum → FREEDOM\nNotcoin → · − · · − ·\nTapSwap → MATRIX\nCATS → MEOW2025\nPixelTap → ⚔️➜🛡️➜🔥\nRocky Rabbit → 3→1→4→2\nYescoin → ←↑→↓←\n+ ще 12 ігор...",
           "premium": "\n<b>Преміум 1$</b> — ранній доступ + сигнали",
           "paid": "Преміум активовано назавжди!",
           "lang_set": "Мову змінено на українську"},
    "ru": {"start": "Привет! @CryptoComboDaily — все комбо и коды в одном месте\n\nВыбери язык:",
           "today": "<b>Комбо на {date}</b>\n\n",
           "combo": "Hamster → Пицца ➜ Кошелёк ➜ Ракета\nBlum → СВОБОДА\nNotcoin → · − · · − ·\nTapSwap → МАТРИЦА\nCATS → МЯУ2025\nPixelTap → ⚔️➜🛡️➜🔥\nRocky Rabbit → 3→1→4→2\nYescoin → ←↑→↓←\n+ ещё 12 игр...",
           "premium": "\n<b>Премиум 1$</b> — ранний доступ + сигналы",
           "paid": "Премиум активирован навсегда!",
           "lang_set": "Язык изменён на русский"},
    "en": {"start": "Hey! @CryptoComboDaily — all combos & codes in one place\n\nChoose language:",
           "today": "<b>Combos {date}</b>\n\n",
           "combo": "Hamster → Pizza ➜ Wallet ➜ Rocket\nBlum → FREEDOM\nNotcoin → · − · · − ·\nTapSwap → MATRIX\nCATS → MEOW2025\nPixelTap → ⚔️➜🛡️➜🔥\nRocky Rabbit → 3→1→4→2\nYescoin → ←↑→↓←\n+ 12 more games...",
           "premium": "\n<b>Premium $1</b> — early access + signals",
           "paid": "Premium activated forever!",
           "lang_set": "Language set to English"}
}

def get_lang(user_id):
    if os.path.exists("lang.json"):
        import json
        try:
            with open("lang.json") as f:
                d = json.load(f)
            return d.get(str(user_id), "en")
        except: pass
    return "en"

def save_lang(user_id, lang):
    import json
    data = {}
    if os.path.exists("lang.json"):
        try:
            with open("lang.json") as f:
                data = json.load(f)
        except: pass
    data[str(user_id)] = lang
    with open("lang.json", "w") as f:
        json.dump(data, f)

# Кнопки — НОВИЙ СИНТАКСИС!
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="English", callback_data="lang_en")],
    [types.InlineKeyboardButton(text="Русский", callback_data="lang_ru")],
    [types.InlineKeyboardButton(text="Українська", callback_data="lang_uk")]
])

main_kb = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="Сьогоднішні комбо / Today")]], resize_keyboard=True)

premium_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="Преміум 1$", url=PAYMENT_LINK)],
    [types.InlineKeyboardButton(text="Я оплатив", callback_data="paid")]
])

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(TEXTS[get_lang(message.from_user.id)]["start"], reply_markup=lang_kb)

@dp.callback_query(lambda c: c.data and c.data.startswith("lang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    save_lang(callback.from_user.id, lang)
    await callback.message.edit_text(TEXTS[lang]["lang_set"], reply_markup=main_kb)
    await callback.answer()

@dp.message(lambda m: any(x in m.text.lower() for x in ["комбо","combo","today"]))
async def combos(message: types.Message):
    lang = get_lang(message.from_user.id)
    text = TEXTS[lang]["today"].format(date=datetime.now().strftime("%d.%m"))
    text += TEXTS[lang]["combo"]
    
    paid = False
    if os.path.exists("paid.txt"):
        with open("paid.txt") as f:
            paid = str(message.from_user.id) in f.read()
    
    if not paid:
        text += TEXTS[lang]["premium"]
        await message.answer(text, reply_markup=premium_kb)
    else:
        await message.answer(text, reply_markup=main_kb)

@dp.callback_query(F.data == "paid")
async def paid(callback: types.CallbackQuery):
    with open("paid.txt", "a") as f:
        f.write(f"{callback.from_user.id}\n")
    lang = get_lang(callback.from_user.id)
    await callback.message.edit_text(TEXTS[lang]["paid"])
    await callback.answer("Активовано!")

async def main():
    print("Бот @CryptoComboDaily запущено!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
