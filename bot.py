import os
import asyncio
import logging
import json
import httpx
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.exceptions import TelegramBadRequest, TelegramUnauthorizedError

# --- КОНФІГУРАЦІЯ ---
# Встановлюємо формат логів, щоб бачити час та рівень
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Коректне перетворення ADMIN_ID
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

# Визначаємо хост та порт для aiohttp
PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_PATH = "/webhook"

# *** КОРЕКТНЕ ВИЗНАЧЕННЯ WEBHOOK URL ДЛЯ RAILWAY ***
# Використовуємо стандартну змінну оточення Railway для домену
RAILWAY_HOST = os.getenv('RAILWAY_STATIC_URL') or os.getenv('RAILWAY_PUBLIC_DOMAIN')

if not BOT_TOKEN:
    raise RuntimeError("КРИТИЧНА ПОМИЛКА: BOT_TOKEN не встановлено!")

if not RAILWAY_HOST:
    logging.warning("RAILWAY_STATIC_URL не встановлено. Бот може не працювати. Використовуємо локальний хост для тестування.")
    # Якщо змінні Railway не встановлені, WEBHOOK_URL буде недійсним, але бот хоча б запуститься локально
    WEBHOOK_URL = f"http://localhost:{PORT}{WEBHOOK_PATH}" 
else:
    # Завжди використовуємо HTTPS для Webhook URL
    WEBHOOK_URL = f"https://{RAILWAY_HOST}{WEBHOOK_PATH}" 

logging.info(f"Використовується Webhook URL: {WEBHOOK_URL}")

# Ініціалізація компонентів aiogram
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === ЗБЕРІГАННЯ ДАНИХ (Volume) ===
DATA_FILE = "/app/data/db.json"
combo_text = "Комбо ще не встановлено"
source_url = ""

def load():
    global combo_text, source_url
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                combo_text = data.get("combo", combo_text)
                source_url = data.get("url", "")
            logging.info("Дані завантажено успішно.")
        except Exception as e:
            logging.error(f"Помилка завантаження: {e}")
    else:
        logging.warning(f"Файл бази даних {DATA_FILE} не знайдено.")

def save():
    os.makedirs("/app/data", exist_ok=True)
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"combo": combo_text, "url": source_url}, f, ensure_ascii=False)
        logging.info("Дані збережено успішно.")
    except Exception as e:
        logging.error(f"Помилка збереження: {e}")

load()

# === Оновлення ===
async def fetch():
    global combo_text
    if not source_url:
        logging.warning("URL для автооновлення відсутній.")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(source_url)
            r.raise_for_status() # Викликає HTTPError для 4xx/5xx
            
            new = r.text.strip()
            if new and new != combo_text:
                logging.info(f"Комбо оновлено: {new[:30]}...")
                combo_text = new
                save()
                if ADMIN_ID and ADMIN_ID != 0:
                    await bot.send_message(ADMIN_ID, "✅ Комбо оновлено автоматично!")
            else:
                logging.info("Комбо не змінилося або отримано пусте значення.")
                
    except Exception as e:
        logging.error(f"Помилка fetch: {e}")

async def scheduler():
    # Чекаємо 30 секунд для стабілізації системи
    await asyncio.sleep(30)
    while True:
        await fetch()
        # Основний інтервал: 24 години
        await asyncio.sleep(24 * 3600)

# Допоміжна функція для відображення адмін-панелі
async def render_admin_panel(c: types.CallbackQuery):
    kb = [
        [types.InlineKeyboardButton(text="Оновити зараз 🔄", callback_data="force")],
        [types.InlineKeyboardButton(text="Головне меню 🏠", callback_data="start")]
    ]
    
    admin_text = (
        "<b>Панель адміністратора</b>\n\n"
        f"Поточне комбо:\n<code>{combo_text}</code>\n\n"
        f"URL для автооновлення: <code>{source_url or 'Не встановлено'}</code>\n\n"
        "Для зміни URL використовуйте команду: <code>/seturl &lt;URL&gt;</code>"
    )

    try:
        await c.message.edit_text(
            admin_text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
        )
    except TelegramBadRequest as e:
        # Ігноруємо помилку, якщо повідомлення не змінилося
        if "message is not modified" not in str(e):
            logging.error(f"Помилка редагування адмін-панелі: {e}")

# === Хендлери ===

@dp.message(CommandStart())
async def start(m: types.Message):
    kb = [[types.InlineKeyboardButton(text="Отримати комбо 🔑", callback_data="getcombo")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка ⚙️", callback_data="admin")])
        
    await m.answer("Привіт! @CryptoComboDaily\nНатисни кнопку:", 
                   reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "getcombo")
async def show_combo(c: types.CallbackQuery):
    # КРИТИЧНО: Підтверджуємо колбек
    await c.answer("Оновлення комбо...")
    
    combo_markup = types.InlineKeyboardMarkup(inline_keyboard=[
         # Змінюємо текст кнопки, щоб показати, що це оновлення
         [types.InlineKeyboardButton(text="Оновити 🔄", callback_data="getcombo")] 
    ])
    
    try:
        # Використовуємо поточний час, щоб контент завжди був різним і не викликав помилку "message is not modified"
        text = f"<b>Комбо на {datetime.now():%d.%m.%Y} оновлено о %H:%M:%S</b>\n\n{combo_text}"
        await c.message.edit_text(
            text,
            reply_markup=combo_markup
        )
    except TelegramBadRequest as e:
        # Дозволяємо ігнорування помилки, якщо вона пов'язана лише з ідентичністю
        if "message is not modified" not in str(e):
            logging.error(f"Помилка редагування комбо: {e}")


@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    # КРИТИЧНО: Підтверджуємо колбек
    await c.answer() 
    
    if c.from_user.id != ADMIN_ID: 
        await c.message.answer("У вас немає доступу до панелі адміністратора.")
        return
        
    await render_admin_panel(c)

@dp.callback_query(F.data == "force")
async def force(c: types.CallbackQuery):
    # КРИТИЧНО: Підтверджуємо колбек
    await c.answer("Запускаю оновлення...")
    
    if c.from_user.id != ADMIN_ID: return
    
    await fetch()
    
    # Оновлюємо адмін-панель після fetch
    await render_admin_panel(c) 

@dp.callback_query(F.data == "start")
async def go_to_start(c: types.CallbackQuery):
    # КРИТИЧНО: Підтверджуємо колбек
    await c.answer()
    
    kb = [[types.InlineKeyboardButton(text="Отримати комбо 🔑", callback_data="getcombo")]]
    if c.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка ⚙️", callback_data="admin")])

    try:
        await c.message.edit_text(
            "Привіт! @CryptoComboDaily\nНатисни кнопку:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
        )
    except TelegramBadRequest:
        # Ігноруємо, якщо повідомлення вже ідентичне
        pass


@dp.message(F.text.startswith("/seturl"))
async def seturl(m: types.Message):
    if m.from_user.id != ADMIN_ID: 
        await m.answer("У вас немає доступу до цієї команди.")
        return
        
    try:
        global source_url
        url_input = m.text.split(maxsplit=1)
        if len(url_input) < 2:
            await m.answer("❌ Використання: <code>/seturl https://...</code>")
            return
            
        source_url = url_input[1].strip()
        save()
        await m.answer(f"✅ URL збережено:\n<code>{source_url}</code>")
        await fetch() # ОНОВЛЮЄМО ОДРАЗУ!
    except Exception as e:
        logging.error(f"Помилка у seturl: {e}")
        await m.answer("❌ Помилка при встановленні URL.")

# === Webhook Запуск ===

async def on_startup(_):
    # !!! ВИДАЛЯЄМО БУДЬ-ЯКІ ПОЛЛІНГИ !!!
    try:
        # Встановлюємо webhook
        await bot.set_webhook(WEBHOOK_URL)
        # Запускаємо планувальник в окремому завданні
        asyncio.create_task(scheduler())
        logging.info(f"✅ БОТ УСПІШНО ЗАПУЩЕНО — РЕЖИМ WEBHOOK: {WEBHOOK_URL}")
    except TelegramUnauthorizedError:
        logging.critical("КРИТИЧНА ПОМИЛКА: Неправильний BOT_TOKEN. Перевірте змінні оточення!")
        await bot.session.close() 
        raise

# Створюємо aiohttp додаток
app = web.Application()
# Додаємо обробник запитів
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
# Реєструємо функцію запуску
app.on_startup.append(on_startup)

if __name__ == "__main__":
    # Запускаємо web-сервер, який буде слухати Webhook-запити
    web.run_app(app, host="0.0.0.0", port=PORT)
