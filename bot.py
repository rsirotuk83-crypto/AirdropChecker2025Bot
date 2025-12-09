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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_PATH = "/webhook"

RAILWAY_HOST = os.getenv('RAILWAY_STATIC_URL') or os.getenv('RAILWAY_PUBLIC_DOMAIN')

if not BOT_TOKEN:
    raise RuntimeError("КРИТИЧНА ПОМИЛКА: BOT_TOKEN не встановлено!")

if not RAILWAY_HOST:
    logging.warning("RAILWAY_STATIC_URL не встановлено.")
    WEBHOOK_URL = f"http://localhost:{PORT}{WEBHOOK_PATH}" 
else:
    WEBHOOK_URL = f"https://{RAILWAY_HOST}{WEBHOOK_PATH}" 

logging.info(f"Налаштований Webhook URL: {WEBHOOK_URL}")

# Ініціалізація компонентів aiogram
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === ЗБЕРІГАННЯ ДАНИХ (Volume) ===
DATA_DIR = "/app/data" 
DATA_FILE = os.path.join(DATA_DIR, "db.json")
combo_text = "Комбо ще не встановлено. Адміністратор, встановіть його командою /setcombo або /seturl." # Фіксоване повідомлення
source_url = "" # URL для автооновлення
last_updated = datetime.now() # Час останнього оновлення

def load():
    """Завантажує дані комбо, URL та час останнього оновлення."""
    global combo_text, source_url, last_updated
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                combo_text = data.get("combo", combo_text)
                source_url = data.get("url", "")
                
                # Завантажуємо час оновлення, якщо є
                updated_str = data.get("updated", "")
                if updated_str:
                    last_updated = datetime.fromisoformat(updated_str)
                
            logging.info("Дані завантажено успішно.")
        except Exception as e:
            logging.error(f"Помилка завантаження даних: {e}")
    else:
        os.makedirs(DATA_DIR, exist_ok=True)
        logging.warning(f"Файл бази даних {DATA_FILE} не знайдено.")

def save():
    """Зберігає дані комбо, URL та час оновлення."""
    global last_updated
    os.makedirs(DATA_DIR, exist_ok=True)
    last_updated = datetime.now()
    try:
        data_to_save = {
            "combo": combo_text,
            "url": source_url,
            "updated": last_updated.isoformat() # Зберігаємо час
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False)
        logging.info("Дані збережено успішно.")
    except Exception as e:
        logging.error(f"Помилка збереження даних: {e}")

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
            
            new_combo = r.text.strip()
            
            if new_combo and new_combo != combo_text:
                logging.info(f"Комбо оновлено: {new_combo[:30]}...")
                combo_text = new_combo
                save()
                
                if ADMIN_ID and ADMIN_ID != 0:
                    await bot.send_message(ADMIN_ID, "✅ Комбо оновлено автоматично!")
            else:
                logging.info("Комбо не змінилося або отримано пусте значення.")
                
    except Exception as e:
        logging.error(f"Помилка fetch: {e}")

async def scheduler():
    """Планувальник, що запускає fetch кожні 24 години."""
    await asyncio.sleep(30) # Затримка для коректного старту Webhook
    while True:
        await fetch()
        await asyncio.sleep(86400) # 24 години

# Допоміжна функція для відображення адмін-панелі
async def render_admin_panel(message: types.Message):
    """Генерує та відправляє (або редагує) адмін-панель."""
    kb = [
        [types.InlineKeyboardButton(text="Оновити зараз 🔄", callback_data="force")],
        [types.InlineKeyboardButton(text="Головне меню 🏠", callback_data="start")]
    ]
    
    admin_text = (
        "<b>Панель адміністратора</b>\n\n"
        f"Поточне комбо:\n<code>{combo_text}</code>\n\n"
        f"URL для автооновлення: <code>{source_url or 'Не встановлено'}</code>\n\n"
        "Для зміни URL: <code>/seturl &lt;URL&gt;</code>\n"
        "Для ручного комбо: <code>/setcombo &lt;Текст комбо&gt;</code>\n"
        f"Останнє оновлення: {last_updated.strftime('%H:%M:%S %d.%m.%Y')}"
    )

    try:
        await message.edit_text(
            admin_text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logging.error(f"Помилка редагування адмін-панелі: {e}")
        # Якщо не вдалося відредагувати, відправляємо нове
        await message.answer(admin_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))


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
    
    # Використовуємо збережений час оновлення для відображення
    text = (
        f"<b>Комбо на сьогодні</b> (оновлено о {last_updated.strftime('%H:%M:%S %d.%m.%Y')})\n\n"
        f"{combo_text}"
    )
    
    try:
        await c.message.edit_text(
            text,
            reply_markup=combo_markup
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logging.error(f"Помилка редагування комбо: {e}")

@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    """Відображає адмін-панель."""
    await c.answer() 
    
    if c.from_user.id != ADMIN_ID: return
        
    await render_admin_panel(c.message) 

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
        await m.answer(f"✅ URL збережено:\n<code>{source_url}</code>\nЗапускаю перше оновлення...")
        await fetch() # ОНОВЛЮЄМО ОДРАЗУ!
    except Exception as e:
        logging.error(f"Помилка у seturl: {e}")
        await m.answer("❌ Помилка при встановленні URL.")

@dp.message(F.text.startswith("/setcombo"))
async def setcombo(m: types.Message):
    """Команда для ручного встановлення тексту комбо."""
    if m.from_user.id != ADMIN_ID: 
        await m.answer("У вас немає доступу до цієї команди.")
        return
        
    try:
        global combo_text
        combo_input = m.text.split(maxsplit=1)
        if len(combo_input) < 2:
            await m.answer("❌ Використання: <code>/setcombo [Ваш текст комбо]</code>")
            return
            
        combo_text = combo_input[1].strip()
        save()
        await m.answer(f"✅ Комбо встановлено вручну та збережено.\n")
    except Exception as e:
        logging.error(f"Помилка у setcombo: {e}")
        await m.answer("❌ Помилка при ручному встановленні комбо.")


# === Webhook Запуск ===

async def on_startup(app: web.Application):
    """Функція, яка викликається при старті aiohttp сервера."""
    try:
        await bot.set_webhook(WEBHOOK_URL)
        asyncio.create_task(scheduler())
        logging.info(f"✅ БОТ УСПІШНО ЗАПУЩЕНО — РЕЖИМ WEBHOOK: {WEBHOOK_URL}")
    except TelegramUnauthorizedError:
        logging.critical("КРИТИЧНА ПОМИЛКА: Неправильний BOT_TOKEN!")
        await bot.session.close() 

app = web.Application()
app.on_startup.append(on_startup)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
