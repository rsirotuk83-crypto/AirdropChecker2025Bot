import os
import asyncio
import logging
import json
import httpx
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# --- 1. КОНФІГУРАЦІЯ ТА ІНІЦІАЛІЗАЦІЯ ---

# Змінні середовища Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
# Порт, який надає Railway (обов'язкова змінна)
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
# Публічний домен, наданий Railway (зазвичай, це змінна RAILWAY_STATIC_URL, але можна використовувати і основний домен)
# Я використаю RAILWAY_STATIC_URL, якщо він доступний.
WEBHOOK_HOST = os.getenv("RAILWAY_STATIC_URL") or os.getenv("YOUR_RAILWAY_DOMAIN") 

if not WEBHOOK_HOST:
    logging.error("Критична помилка: Не знайдено публічний домен (RAILWAY_STATIC_URL або YOUR_RAILWAY_DOMAIN).")
    
WEBHOOK_PATH = "/webhook/"
WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- 2. ПЕРСИСТЕНТНЕ ЗБЕРІГАННЯ ДАНИХ (db.json) ---
DATA_DIR = Path("data")
DB_FILE = DATA_DIR / "db.json"

# Початкові значення
db_data = {
    "combo_text": "Комбо ще не встановлено",
    "source_url": ""
}

def load_data():
    """Завантажує дані з JSON-файлу або ініціалізує, якщо файл не існує."""
    global db_data
    DATA_DIR.mkdir(exist_ok=True)
    if DB_FILE.exists():
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                db_data.update(json.load(f))
            logging.info("Дані конфігурації успішно завантажено.")
        except Exception as e:
            logging.error(f"Помилка читання DB.JSON: {e}. Використовуються початкові значення.")
    else:
        logging.warning(f"Файл бази даних {DB_FILE} не знайдено. Будуть використані початкові значення.")
        save_data() # Створюємо файл
        
def save_data():
    """Зберігає поточні дані в JSON-файл."""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db_data, f, ensure_ascii=False, indent=4)
        logging.info("Дані успішно збережено.")
    except Exception as e:
        logging.error(f"Помилка запису DB.JSON: {e}")

# --- 3. АВТООНОВЛЕННЯ З HTTP-ДЖЕРЕЛА ---
async def fetch():
    source_url = db_data.get("source_url")
    if not source_url:
        logging.warning("URL для автооновлення відсутній.")
        return
    
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(source_url)
            r.raise_for_status() 
            
            new = r.text.strip()
            
            if new and new != db_data["combo_text"]:
                db_data["combo_text"] = new
                save_data()
                logging.info(f"Комбо оновлено: {new[:50]}...")
                if ADMIN_ID:
                    await bot.send_message(ADMIN_ID, "✅ Комбо автоматично оновлено!")
            elif new and new == db_data["combo_text"]:
                 logging.info("Комбо не змінилося.")
            else:
                 logging.warning("Отримано порожній контент з джерела.")

    except Exception as e:
        error_msg = f"Помилка автооновлення: {e.__class__.__name__}: {e}"
        logging.error(error_msg)
        if ADMIN_ID:
            # На Webhook ми не можемо використовувати фонові задачі для адміна, 
            # тому цю логіку залишаємо для Polling. Але для Webhook-бота, 
            # якщо fetch викликається планувальником, ми можемо залишити повідомлення.
            await bot.send_message(ADMIN_ID, f"❌ Помилка автооновлення: {error_msg}")


# === ХЕНДЛЕРИ КОМАНД І КНОПОК ===

@dp.message(CommandStart())
async def start(m: types.Message):
    kb = [[types.InlineKeyboardButton(text="🎁 Отримати комбо", callback_data="combo")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="🛠 Адмінка", callback_data="admin")])
    
    await m.answer(
        "👋 Привіт! <b>@CryptoComboDaily</b>\nЯ надаю актуальні щоденні комбінації.\nНатисни кнопку нижче:", 
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(F.data == "combo")
async def show_combo(c: types.CallbackQuery):
    await c.answer("Оновлюю інформацію...")
    
    combo_text = db_data.get("combo_text", "Комбо ще не встановлено")
    
    text_to_display = (
        f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n"
        f"{combo_text}"
    )
    
    try:
        await c.message.edit_text(
            text_to_display, 
            parse_mode="HTML",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🎁 Отримати комбо", callback_data="combo")]
            ])
        )
    except TelegramAPIError as e:
        if "message is not modified" in str(e):
            logging.info("Редагування пропущено: текст не змінився.")
            await c.answer("Комбо вже актуальне!", show_alert=False) 
        else:
            logging.error(f"Помилка при редагуванні повідомлення: {e}")
            await c.answer("Помилка редагування. Спробуйте команду /start знову.", show_alert=True)


@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("Доступ заборонено!", show_alert=True)
        return
    await c.answer() 
    
    source_url = db_data.get("source_url", "")
    
    await c.message.edit_text(
        f"<b>Адмінка</b>\nПоточний URL: <code>{source_url or 'НЕ ВСТАНОВЛЕНО'}</code>", 
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔄 Оновити зараз", callback_data="force")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start")] 
        ])
    )
    
@dp.callback_query(F.data == "start")
async def back_to_start(c: types.CallbackQuery):
    await c.answer()
    await start(c.message)


@dp.callback_query(F.data == "force")
async def force(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("Доступ заборонено!", show_alert=True)
        return
    
    await c.answer("Запускаю примусове оновлення...")
    await fetch()
    
    await c.message.edit_text("✅ Оновлено! Перевірте лог або запустіть /combo", 
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")]
        ])
    )

@dp.message(F.text.startswith("/seturl"))
async def seturl(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    try:
        new_url = m.text.split(maxsplit=1)[1].strip()
        db_data["source_url"] = new_url
        save_data()
        await m.answer(f"✅ URL збережено та встановлено як джерело:\n<code>{new_url}</code>")
        await fetch() 
    except IndexError:
        await m.answer("Використання: <code>/seturl https://example.com/daily.txt</code>")

@dp.message(F.text.startswith("/setcombo"))
async def setcombo(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    new_combo = m.text.partition(" ")[2].strip()
    
    if new_combo:
        db_data["combo_text"] = new_combo
        save_data()
        await m.answer("✅ Комбо збережено вручну.")
    else:
        await m.answer("Будь ласка, вкажіть текст комбо після команди. Наприклад: <code>/setcombo Карта А -> 1M</code>")

# --- 4. ЗАПУСК WEBHOOK ТА ПЛАНУВАЛЬНИКА ---

async def on_startup(dispatcher: Dispatcher, bot: Bot):
    """Виконується один раз при запуску сервера."""
    logging.info("Завантаження даних та встановлення Webhook...")
    load_data() # Завантажуємо дані з db.json
    
    # Встановлюємо Webhook на Telegram API
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook встановлено: {WEBHOOK_URL}")

    # Запускаємо фонову задачу планувальника (якщо це можливо на вашому хостингу)
    # Зверніть увагу: на деяких хостингах, які не підтримують фонові процеси, це може не спрацювати.
    asyncio.create_task(scheduler())


async def scheduler():
    """Планувальник для щоденного оновлення."""
    logging.info("Планувальник запущено.")
    await asyncio.sleep(30) # Чекаємо 30 секунд після старту
    while True:
        logging.info("Планувальник: Запуск оновлення комбо...")
        await fetch()
        await asyncio.sleep(24 * 3600) # Чекаємо 24 години

# === ОСНОВНА ФУНКЦІЯ ЗАПУСКУ ===
def main():
    if not BOT_TOKEN:
        logging.error("Критична помилка: BOT_TOKEN не встановлено.")
        return

    # 1. Створення додатку aiohttp
    app = web.Application()
    
    # 2. Налаштування обробника Telegram
    # Webhook буде приймати запити лише за шляхом WEBHOOK_PATH
    request_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        # На Railway ми можемо пропустити check_ip, оскільки це може спричинити проблеми
    )
    request_handler.register(app, path=WEBHOOK_PATH)

    # 3. Встановлення хендлерів запуску та зупинки
    app.on_startup.append(lambda app: on_startup(dp, bot))
    # app.on_shutdown.append(on_shutdown) # Можна додати логіку очищення при зупинці

    # 4. Запуск веб-сервера
    logging.info(f"🚀 Запуск Webhook сервера на порту {WEB_SERVER_PORT}...")
    web.run_app(app, host="0.0.0.0", port=WEB_SERVER_PORT)


if __name__ == "__main__":
    main()
