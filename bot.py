import os
import asyncio
import json
import logging
import httpx
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ===================== НАЛАШТУВАННЯ =====================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not ADMIN_ID:
    logging.error("Не встановлено BOT_TOKEN або ADMIN_ID")
    exit(1)

# ===================== СТАН =====================
DB_FILE = "db_state.json"
USER_SUBSCRIPTIONS: dict[int, bool] = {}
IS_ACTIVE = False
COMBO_CONTENT = "Комбо ще не встановлено.\nВикористай /seturl щоб налаштувати автооновлення."
AUTO_SOURCE_URL = ""   # ← тут буде твій .txt URL

# ===================== ПЕРСИСТЕНТНІСТЬ =====================
def load_state():
    global USER_SUBSCRIPTIONS, IS_ACTIVE, COMBO_CONTENT, AUTO_SOURCE_URL
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                USER_SUBSCRIPTIONS = {int(k): v for k, v in data.get("subs", {}).items()}
                IS_ACTIVE = data.get("active", False)
                COMBO_CONTENT = data.get("combo", COMBO_CONTENT)
                AUTO_SOURCE_URL = data.get("url", "")
            logging.info("Стан завантажено")
        except Exception as e:
            logging.error(f"Помилка завантаження: {e}")

def save_state():
    data = {
        "subs": USER_SUBSCRIPTIONS,
        "active": IS_ACTIVE,
        "combo": COMBO_CONTENT,
        "url": AUTO_SOURCE_URL
    }
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Помилка збереження: {e}")

load_state()

# ===================== БОТ =====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()

# ===================== АВТООНОВЛЕННЯ =====================
async def fetch_combo():
    global COMBO_CONTENT
    if not AUTO_SOURCE_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(AUTO_SOURCE_URL)
            r.raise_for_status()
            new = r.text.strip()
            if new and new != COMBO_CONTENT:
                COMBO_CONTENT = new
                save_state()
                logging.info("Комбо оновлено автоматично")
                await bot.send_message(ADMIN_ID, "Комбо автоматично оновлено!")
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"Помилка автооновлення:\n{e}")

async def scheduler():
    await asyncio.sleep(20)
    while True:
        await fetch_combo()
        await asyncio.sleep(24 * 3600)   # раз на добу

# ===================== ХЕНДЛЕРИ =====================
@dp.message(CommandStart())
async def start(msg: types.Message):
    uid = msg.from_user.id
    name = msg.from_user.first_name or "друже"
    premium = USER_SUBSCRIPTIONS.get(uid, False)

    text = f"Привіт, **{name}**!\n\n"
    if uid == ADMIN_ID:
        text += f"Автооновлення: {'включено' if AUTO_SOURCE_URL else 'вимкнено'}\n\n"

    kb = [[types.InlineKeyboardButton(text="Отримати комбо", callback_data="combo")]]
    if uid == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка", callback_data="admin")])
    elif not premium:
        kb.insert(0, [types.InlineKeyboardButton(text="Купити преміум 1 TON", callback_data="buy")])

    await msg.answer(text + "Обери дію:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "combo")
async def send_combo(cb: types.CallbackQuery):
    uid = cb.from_user.id
    if uid == ADMIN_ID or IS_ACTIVE or USER_SUBSCRIPTIONS.get(uid, False):
        date = datetime.now().strftime("%d.%m.%Y")
        text = f"**Комбо та коди на {date}**\n\n{COMBO_CONTENT}"
        await cb.message.edit_text(text, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await cb.answer("Тільки для преміум-користувачів", show_alert=True)

@dp.callback_query(F.data == "buy")
async def buy_premium(cb: types.CallbackQuery):
    await cb.answer("Оплата 1 TON — функція підключається за 2 хвилини, якщо треба", show_alert=True)

@dp.callback_query(F.data == "admin")
async def admin_panel(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    kb = [
        [types.InlineKeyboardButton(text="Оновити комбо зараз", callback_data="force")],
        [types.InlineKeyboardButton(text="Активувати для всіх", callback_data="activate")],
        [types.InlineKeyboardButton(text="Деактивувати для всіх", callback_data="deactivate")],
    ]
    await cb.message.edit_text("Адмін-панель", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.in_({"force", "activate", "deactivate"}))
async def admin_actions(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    if cb.data == "force":
        await fetch_combo()
        await cb.answer("Примусово оновлено")
    elif cb.data == "activate":
        global IS_ACTIVE
        IS_ACTIVE = True
        save_state()
        await cb.answer("Активовано для всіх")
    elif cb.data == "deactivate":
        global IS_ACTIVE
        IS_ACTIVE = False
        save_state()
        await cb.answer("Деактивовано для всіх")

# адмін-команди
@dp.message(Command("seturl"))
async def set_url(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    try:
        url = msg.text.split(maxsplit=1)[1]
        global AUTO_SOURCE_URL
        AUTO_SOURCE_URL = url
        save_state()
        await msg.answer(f"URL встановлено:\n{url}\nПерше оновлення за хвилину")
    except:
        await msg.answer("Використання: /seturl https://example.com/combo.txt")

# ===================== ЗАПУСК =====================
async def main():
    asyncio.create_task(scheduler())
    logging.info("БОТ УСПІШНО ЗАПУЩЕНО — ГОТОВИЙ")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
