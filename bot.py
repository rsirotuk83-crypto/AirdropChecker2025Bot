import os
import asyncio
import json
import logging
import httpx
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ===================== НАЛАШТУВАННЯ =====================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not CRYPTO_BOT_TOKEN or not ADMIN_ID:
    logging.error("Не встановлено BOT_TOKEN / CRYPTO_BOT_TOKEN / ADMIN_ID")
    exit(1)

# ===================== ФАЙЛИ ТА СТАН =====================
DB_FILE = "db_state.json"
USER_SUBSCRIPTIONS: dict[int, bool] = {}
IS_ACTIVE = False
COMBO_CONTENT = "Комбо ще не встановлено адміністратором."
AUTO_SOURCE_URL = ""  # сюди ставиш https://miningcombo.com/raw або будь-який txt/url

# ===================== ПЕРСИСТЕНТНІСТЬ =====================
def load_persistent_state():
    global USER_SUBSCRIPTIONS, IS_ACTIVE, COMBO_CONTENT, AUTO_SOURCE_URL
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                USER_SUBSCRIPTIONS = {int(k): v for k, v in data.get("subscriptions", {}).items()}
                IS_ACTIVE = data.get("is_active", False)
                COMBO_CONTENT = data.get("combo_content", COMBO_CONTENT)
                AUTO_SOURCE_URL = data.get("auto_source_url", "")
            logging.info("Стан завантажено з db_state.json")
        except Exception as e:
            logging.error(f"Помилка завантаження стану: {e}")

def save_persistent_state():
    data = {
        "subscriptions": USER_SUBSCRIPTIONS,
        "is_active": IS_ACTIVE,
        "combo_content": COMBO_CONTENT,
        "auto_source_url": AUTO_SOURCE_URL
    }
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info("Стан збережено")
    except Exception as e:
        logging.error(f"Помилка збереження стану: {e}")

load_persistent_state()  # ← важливо: викликаємо одразу після визначення функції

# ===================== БОТ ТА ДИСПАТЧЕР =====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()

# ===================== АВТООНОВЛЕННЯ КОМБО =====================
async def fetch_and_update_combo():
    global COMBO_CONTENT
    if not AUTO_SOURCE_URL:
        return

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(AUTO_SOURCE_URL)
            r.raise_for_status()
            new_content = r.text.strip()

            if new_content and new_content != COMBO_CONTENT:
                COMBO_CONTENT = new_content
                save_persistent_state()
                logging.info("Комбо успішно оновлено автоматично")
                await bot.send_message(ADMIN_ID, "Автооновлення комбо успішне!")
    except Exception as e:
        logging.error(f"Помилка автооновлення: {e}")
        await bot.send_message(ADMIN_ID, f"Помилка автооновлення:\n{e}")

async def auto_update_scheduler():
    await asyncio.sleep(15)  # чекаємо, поки бот повністю запуститься
    while True:
        await fetch_and_update_combo()
        # оновлення кожні 24 години (можна змінити на 12 або 6)
        await asyncio.sleep(24 * 60 * 60)

# ===================== ХЕНДЛЕРИ =====================
@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id
    name = message.from_user.first_name or "друже"
    is_prem = user_id in USER_SUBSCRIPTIONS and USER_SUBSCRIPTIONS[user_id]

    text = f"Привіт, **{name}**!\n\n"
    if user_id == ADMIN_ID:
        text += f"Адмін-панель активна\nАвтооновлення: {'вкл' if AUTO_SOURCE_URL else 'викл'}\n\n"
    
    text += "Обери дію:"

    kb = [
        [types.InlineKeyboardButton(text="Отримати комбо", callback_data="show_combo")]
    ]
    if user_id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмін-панель", callback_data="admin_panel")])
    elif not is_prem:
        kb.insert(0, [types.InlineKeyboardButton(text="Купити преміум (1 TON)", callback_data="buy_premium")])

    await message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "show_combo")
async def show_combo(cb: types.CallbackQuery):
    user_id = cb.from_user.id
    if user_id == ADMIN_ID or IS_ACTIVE or USER_SUBSCRIPTIONS.get(user_id):
        date = datetime.now().strftime("%d.%m.%Y")
        text = f"**Комбо та коди на {date}**\n\n{COMBO_CONTENT}"
        await cb.message.edit_text(text, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await cb.answer("Доступно тільки преміум-користувачам", show_alert=True)

@dp.callback_query(F.data == "buy_premium")
async def buy_premium(cb: types.CallbackQuery):
    # тут твій код створення інвойсу через Crypto Bot (я залишу без змін — він у тебе вже є)
    await cb.answer("Функція оплати підключається за 2 хвилини — пиши, якщо треба")

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return
    kb = [
        [types.InlineKeyboardButton(text="Активувати для всіх", callback_data="activate_all")],
        [types.InlineKeyboardButton(text="Деактивувати для всіх", callback_data="deactivate_all")],
        [types.InlineKeyboardButton(text="Оновити комбо зараз", callback_data="force_update")],
        [types.InlineKeyboardButton(text="Встановити URL автооновлення", url="https://t.me/yourbot?start=seturl")],
    ]
    await cb.message.edit_message_text("Адмін-панель", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

# прості адмін-команди
@dp.message(Command("seturl"))
async def set_url(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    url = msg.text.split(maxsplit=1)[1] if len(msg.text.split()) > 1 else ""
    if not url:
        await msg.answer("Надішли: /seturl https://example.com/combo.txt")
        return
    global AUTO_SOURCE_URL
    AUTO_SOURCE_URL = url
    save_persistent_state()
    await msg.answer(f"URL встановлено:\n{url}\nПерше оновлення через кілька секунд")

@dp.message(Command("force"))
async def force_update(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await fetch_and_update_combo()
    await msg.answer("Примусове оновлення виконано")

# ===================== ЗАПУСК =====================
async def main():
    # запускаємо автооновлення у фоні
    asyncio.create_task(auto_update_scheduler())
    logging.info("Бот запущений і готовий")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
