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

# Додаємо імпорт для обробки помилок редагування
from aiogram.exceptions import TelegramBadRequest 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_PATH = "/webhook"
# Встановлюємо host явно, якщо railway_static_url не спрацює
RAILWAY_HOST = os.getenv('RAILWAY_STATIC_URL') or os.getenv('RAILWAY_PUBLIC_DOMAIN')
if not RAILWAY_HOST:
    logging.warning("RAILWAY_STATIC_URL не встановлено, використовується заглушка. Webhook не буде працювати без коректної змінної оточення.")
    WEBHOOK_URL = f"http://localhost:8080{WEBHOOK_PATH}" 
else:
    # Використовуємо HTTPS, що є стандартом для Telegram
    WEBHOOK_URL = f"https://{RAILWAY_HOST}{WEBHOOK_PATH}" 

# Використовуємо HTML, оскільки він простіший для базового форматування
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === Дані в Volume ===
DATA_FILE = "/app/data/db.json"
combo_text = "Комбо ще не встановлено"
source_url = ""

def load():
    global combo_text, source_url
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                combo_text = d.get("combo", combo_text)
                source_url = d.get("url", "")
            logging.info("Дані завантажено успішно.")
        except Exception as e: 
            logging.error(f"Помилка завантаження даних з {DATA_FILE}: {e}")
            pass

def save():
    try:
        os.makedirs("/app/data", exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"combo": combo_text, "url": source_url}, f, ensure_ascii=False, indent=4)
        logging.info("Дані збережено успішно.")
    except Exception as e:
         logging.error(f"Помилка збереження даних у {DATA_FILE}: {e}")

load()

async def fetch():
    global combo_text
    if not source_url: 
        logging.warning("URL для автооновлення відсутній.")
        return
        
    logging.info(f"Запуск скрапінгу з URL: {source_url}")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(source_url)
            if r.status_code == 200:
                new = r.text.strip()
                if new and new != combo_text:
                    logging.info(f"Комбо оновлено. Старе: {combo_text[:30]}..., Нове: {new[:30]}...")
                    combo_text = new
                    save()
                    if ADMIN_ID and ADMIN_ID != 0:
                        try:
                            await bot.send_message(ADMIN_ID, "✅ Комбо оновлено за розкладом!")
                        except Exception as e:
                            logging.error(f"Не вдалося надіслати повідомлення адміну: {e}")
                else:
                    logging.info("Комбо не змінилося або отримано пусте значення.")
            else:
                logging.error(f"Помилка HTTP {r.status_code} при отриманні комбо з {source_url}")
                
    except Exception as e: 
        logging.error(f"Критична помилка під час fetch: {e}")

async def scheduler():
    # Чекаємо 30 секунд після старту перед першим запуском, щоб дати час ініціалізації
    await asyncio.sleep(30) 
    while True:
        await fetch()
        # Основний інтервал: 24 години
        await asyncio.sleep(24 * 3600) 

# --- HANDLERS ---

@dp.message(CommandStart())
async def start(m: types.Message):
    kb = [[types.InlineKeyboardButton(text="Отримати комбо 🔑", callback_data="get_combo")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка ⚙️", callback_data="admin")])
    
    # Використовуємо HTML для коректного відображення посилання, якщо це потрібно
    await m.answer("Привіт! @CryptoComboDaily\nНатисни кнопку:", 
                   reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb),
                   parse_mode=ParseMode.HTML) 

@dp.callback_query(F.data == "get_combo")
async def show_combo(c: types.CallbackQuery):
    # 1. Головне виправлення: Відповідаємо на колбек, щоб прибрати "годинник"
    await c.answer() 
    
    # 2. Надсилаємо НОВЕ повідомлення, замість редагування стартового (краще UX)
    text = f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo_text}"
    
    # Використовуємо .answer(), а не edit_text()
    await c.message.answer(text, parse_mode="HTML")

@dp.callback_query(F.data == "admin")
async def show_admin_panel(c: types.CallbackQuery):
    # 1. Відповідаємо на колбек, щоб прибрати "годинник"
    await c.answer()

    if c.from_user.id != ADMIN_ID: 
        await c.message.answer("У вас немає доступу до панелі адміністратора.", parse_mode="HTML")
        return
        
    kb = [
        [types.InlineKeyboardButton(text="Оновити комбо зараз 🔄", callback_data="fetch_now")],
        [types.InlineKeyboardButton(text="Головне меню 🏠", callback_data="start")]
    ]
    
    # Формуємо текст панелі адміністратора
    admin_text = (
        "<b>Панель адміністратора</b>\n\n"
        f"Поточне комбо:\n{combo_text}\n\n"
        f"URL для автооновлення: <code>{source_url or 'Не встановлено'}</code>\n\n"
        "Для зміни URL використовуйте команду: <code>/seturl &lt;URL&gt;</code>"
    )

    try:
        # Намагаємося відредагувати повідомлення
        await c.message.edit_text(
            admin_text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        # Це обробляє помилку "message is not modified"
        if "message is not modified" in str(e):
            logging.info("Admin panel message content is identical, skipping edit.")
            # Не робимо нічого, просто ігноруємо
        else:
            logging.error(f"Помилка редагування адмін-панелі: {e}")
            
@dp.callback_query(F.data == "start")
async def go_to_start(c: types.CallbackQuery):
    # Хендлер для повернення до головного меню (викликає команду start, але через edit_text)
    await c.answer()
    kb = [[types.InlineKeyboardButton(text="Отримати комбо 🔑", callback_data="get_combo")]]
    if c.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка ⚙️", callback_data="admin")])

    try:
        await c.message.edit_text(
            "Привіт! @CryptoComboDaily\nНатисни кнопку:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode=ParseMode.HTML
        )
    except TelegramBadRequest:
        # Ігноруємо, якщо повідомлення вже ідентичне
        pass

@dp.callback_query(F.data == "fetch_now")
async def fetch_now_handler(c: types.CallbackQuery):
    await c.answer("Запускаю негайне оновлення комбо...")
    
    if not source_url:
        await c.message.answer("❌ URL для автооновлення не встановлено. Встановіть його командою /seturl")
    else:
        await c.message.answer("Починаю примусовий fetch...")
        await fetch() # Викликаємо функцію оновлення
        await show_admin_panel(c) # Оновлюємо панель адміністратора

@dp.message(F.text.startswith("/seturl"))
async def seturl(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        global source_url
        url_input = m.text.split(maxsplit=1)
        if len(url_input) < 2:
             await m.answer("❌ Використання: <code>/seturl https://...</code>", parse_mode="HTML")
             return
             
        source_url = url_input[1].strip()
        save()
        await m.answer(f"✅ URL збережено:\n<code>{source_url}</code>", parse_mode="HTML")
        await fetch() # Оновлюємо одразу після встановлення URL
    except Exception as e:
        logging.error(f"Помилка у seturl: {e}")
        await m.answer("❌ Помилка при встановленні URL.")

# === Webhook ===
app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

async def on_startup(_):
    # При старті встановлюємо webhook і запускаємо планувальник
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(scheduler())
    logging.info(f"Webhook встановлено на: {WEBHOOK_URL}")
    if RAILWAY_HOST:
        logging.info(f"Railway Host: {RAILWAY_HOST}")


app.on_startup.append(on_startup)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
