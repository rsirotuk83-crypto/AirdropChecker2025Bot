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
# Налаштування логування для відображення часу та рівня
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")

try:
    # Коректне перетворення ADMIN_ID
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

# Визначаємо хост та порт для aiohttp. PORT має бути встановлено Railway.
PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_PATH = "/webhook"

# *** КОРЕКТНЕ ВИЗНАЧЕННЯ WEBHOOK URL ДЛЯ RAILWAY ***
# Використовуємо змінні оточення Railway для домену
RAILWAY_HOST = os.getenv('RAILWAY_STATIC_URL') or os.getenv('RAILWAY_PUBLIC_DOMAIN')

if not BOT_TOKEN:
    # Критична помилка, якщо токен відсутній
    raise RuntimeError("КРИТИЧНА ПОМИЛКА: BOT_TOKEN не встановлено!")

# Формуємо фінальний Webhook URL
if not RAILWAY_HOST:
    logging.warning("RAILWAY_STATIC_URL не встановлено. Використовуємо localhost, що не буде працювати на Railway.")
    WEBHOOK_URL = f"http://localhost:{PORT}{WEBHOOK_PATH}" 
else:
    WEBHOOK_URL = f"https://{RAILWAY_HOST}{WEBHOOK_PATH}" 

logging.info(f"Налаштований Webhook URL: {WEBHOOK_URL}")

# Ініціалізація компонентів aiogram
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === ЗБЕРІГАННЯ ДАНИХ (Volume) ===
# Шлях до директорії даних, має збігатися з mountPath у railway.toml
DATA_DIR = "/app/data" 
DATA_FILE = os.path.join(DATA_DIR, "db.json")
combo_text = "Комбо ще не встановлено" # Значення за замовчуванням
source_url = "" # URL для автооновлення

def load():
    """Завантажує дані комбо та URL з дискового Volume."""
    global combo_text, source_url
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                combo_text = data.get("combo", combo_text)
                source_url = data.get("url", "")
            logging.info("Дані завантажено успішно.")
        except Exception as e:
            logging.error(f"Помилка завантаження даних: {e}")
    else:
        os.makedirs(DATA_DIR, exist_ok=True)
        logging.warning(f"Файл бази даних {DATA_FILE} не знайдено.")

def save():
    """Зберігає дані комбо та URL на дисковий Volume."""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"combo": combo_text, "url": source_url}, f, ensure_ascii=False)
        logging.info("Дані збережено успішно.")
    except Exception as e:
        logging.error(f"Помилка збереження даних: {e}")

# Завантажуємо дані при старті
load()

# === АВТООНОВЛЕННЯ (Scheduler) ===
async def fetch():
    """Виконує запит до джерела та оновлює комбо."""
    global combo_text
    if not source_url:
        logging.warning("URL для автооновлення відсутній. Пропускаю fetch.")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(source_url)
            r.raise_for_status()
            
            # Припускаємо, що джерело повертає чистий текст комбо
            new_combo = r.text.strip()
            
            if new_combo and new_combo != combo_text:
                logging.info(f"Комбо оновлено: {new_combo[:30]}...")
                combo_text = new_combo
                save()
                
                # Повідомлення адміну про успішне оновлення
                if ADMIN_ID and ADMIN_ID != 0:
                    await bot.send_message(ADMIN_ID, "✅ Комбо оновлено автоматично!")
            else:
                logging.info("Комбо не змінилося або отримано пусте значення.")
                
    except Exception as e:
        logging.error(f"Помилка fetch: {e}")

async def scheduler():
    """Планувальник, що запускає fetch кожні 24 години."""
    # Чекаємо 30 секунд після запуску, щоб дозволити Webhook налаштуватися
    await asyncio.sleep(30) 
    while True:
        await fetch()
        # Чекаємо 24 години (86400 секунд)
        await asyncio.sleep(86400) 

# === Хендлери ===

@dp.message(CommandStart())
async def start_handler(m: types.Message):
    """Обробник команди /start."""
    kb = [[types.InlineKeyboardButton(text="Отримати комбо 🔑", callback_data="getcombo")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка ⚙️", callback_data="admin")])
        
    await m.answer("Привіт! AirdropChecker2025Bot\nНатисни кнопку:", 
                   reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "getcombo")
async def show_combo(c: types.CallbackQuery):
    """Обробник кнопки 'Отримати комбо'."""
    await c.answer("Оновлення комбо...")
    
    combo_markup = types.InlineKeyboardMarkup(inline_keyboard=[
         [types.InlineKeyboardButton(text="Оновити 🔄", callback_data="getcombo")] 
    ])
    
    # Додаємо час до тексту, щоб уникнути помилки "message is not modified"
    text = (
        f"<b>Комбо на сьогодні</b> (оновлено о {datetime.now():%H:%M:%S})\n\n"
        f"{combo_text}"
    )
    
    try:
        await c.message.edit_text(
            text,
            reply_markup=combo_markup
        )
    except TelegramBadRequest as e:
        # Ігноруємо помилку, якщо текст ідентичний (хоча час має це виправити)
        if "message is not modified" not in str(e):
            logging.error(f"Помилка редагування комбо: {e}")

@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    """Відображає адмін-панель."""
    await c.answer() 
    
    if c.from_user.id != ADMIN_ID: 
        await c.message.answer("У вас немає доступу до панелі адміністратора.")
        return
        
    await render_admin_panel(c.message) # Передаємо message об'єкт

async def render_admin_panel(message: types.Message):
    """Генерує та відправляє (або редагує) адмін-панель."""
    kb = [
        [types.InlineKeyboardButton(text="Оновити зараз 🔄", callback_data="force")],
        [types.InlineKeyboardButton(text="Головне меню 🏠", callback_data="start")]
    ]
    
    admin_text = (
        "<b>Панель адміністратора</b>\n\n"
        f"Поточне комбо: <code>{combo_text}</code>\n\n"
        f"URL для автооновлення: <code>{source_url or 'Не встановлено'}</code>\n\n"
        "Для зміни URL використовуйте команду: <code>/seturl &lt;URL&gt;</code>"
    )

    try:
        # Намагаємося редагувати повідомлення, якщо це колбек
        await message.edit_text(
            admin_text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
        )
    except Exception:
        # Якщо не вдалося відредагувати (наприклад, це було повідомлення /start), відправляємо нове
        await message.answer(
            admin_text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
        )


@dp.callback_query(F.data == "force")
async def force_update(c: types.CallbackQuery):
    """Обробник кнопки 'Оновити зараз'."""
    await c.answer("Запускаю оновлення...")
    
    if c.from_user.id != ADMIN_ID: return
    
    await fetch()
    
    await render_admin_panel(c.message) 

@dp.callback_query(F.data == "start")
async def go_to_start(c: types.CallbackQuery):
    """Обробник кнопки 'Головне меню'."""
    await c.answer()
    
    kb = [[types.InlineKeyboardButton(text="Отримати комбо 🔑", callback_data="getcombo")]]
    if c.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка ⚙️", callback_data="admin")])

    try:
        await c.message.edit_text(
            "Привіт! AirdropChecker2025Bot\nНатисни кнопку:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
        )
    except TelegramBadRequest:
        pass


@dp.message(F.text.startswith("/seturl"))
async def seturl(m: types.Message):
    """Команда для встановлення URL для автооновлення."""
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

# === Webhook Запуск — КЛЮЧОВА СЕКЦІЯ WEBHOOK ===

async def on_startup(app: web.Application):
    """Функція, яка викликається при старті aiohttp сервера."""
    try:
        # Встановлюємо webhook (надсилаємо URL до Telegram)
        await bot.set_webhook(WEBHOOK_URL)
        # Запускаємо планувальник в окремому завданні
        asyncio.create_task(scheduler())
        logging.info(f"✅ БОТ УСПІШНО ЗАПУЩЕНО — РЕЖИМ WEBHOOK: {WEBHOOK_URL}")
    except TelegramUnauthorizedError:
        logging.critical("КРИТИЧНА ПОМИЛКА: Неправильний BOT_TOKEN. Перевірте змінні оточення!")
        # Закриваємо сесію, оскільки без токена робота неможлива
        await bot.session.close() 

# Створюємо aiohttp додаток
app = web.Application()
# Реєструємо функцію запуску
app.on_startup.append(on_startup)
# Додаємо обробник запитів, які надсилає Telegram
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)


if __name__ == "__main__":
    # ЦЕ ЄДИНА КОМАНДА ЗАПУСКУ, ЯКА ВИКЛЮЧАЄ ПОЛЛІНГ:
    # web.run_app() запускає aiohttp-сервер, який чекає на Webhook-запити
    logging.info(f"Запуск aiohttp сервера на 0.0.0.0:{PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)
