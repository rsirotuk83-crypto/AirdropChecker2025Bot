import os
import asyncio
import logging
import json
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.exceptions import TelegramBadRequest, TelegramUnauthorizedError

# Імпортуємо функцію скрепінгу з hamster_scraper.py
try:
    from hamster_scraper import scrape_for_combo
except ImportError:
    logging.critical("Помилка імпорту: hamster_scraper.py не знайдено.")
    raise

# --- КОНФІГУРАЦІЯ ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - Bot - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ADMIN_ID використовується для доступу до адмін-команд /setcombo та панелі
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

PORT = int(os.getenv("PORT", "8080"))
WEBHOOK_PATH = "/webhook"
RAILWAY_HOST = os.getenv('RAILWAY_STATIC_URL') or os.getenv('RAILWAY_PUBLIC_DOMAIN')
UPDATE_INTERVAL_SECONDS = 3 * 60 * 60 # Інтервал оновлення: 3 години

if not BOT_TOKEN:
    raise RuntimeError("КРИТИЧНА ПОМИЛКА: BOT_TOKEN не встановлено!")

# Формуємо публічний URL для Webhook
WEBHOOK_URL = f"https://{RAILWAY_HOST}{WEBHOOK_PATH}" if RAILWAY_HOST else f"http://localhost:{PORT}{WEBHOOK_PATH}" 
logging.info(f("Налаштований Webhook URL: {WEBHOOK_URL}")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === ЗБЕРІГАННЯ ДАНИХ (Volume) ===
# DATA_DIR має відповідати mountPath у railway.toml
DATA_DIR = "/app/data" 
DATA_FILE = os.path.join(DATA_DIR, "db.json")

# Глобальні змінні
DEFAULT_COMBO = "Комбо ще не встановлено. Адміністратор, встановіть його вручну (/setcombo) або дочекайтеся першого запуску скрепера."
combo_text = DEFAULT_COMBO
last_updated = datetime.now() 

def load():
    """Завантажує дані комбо та час останнього оновлення."""
    global combo_text, last_updated
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                combo_text = data.get("combo", combo_text)
                
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
    """Зберігає дані комбо та час оновлення."""
    global last_updated
    os.makedirs(DATA_DIR, exist_ok=True)
    last_updated = datetime.now()
    try:
        data_to_save = {
            "combo": combo_text,
            "updated": last_updated.isoformat()
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False)
        logging.info("Дані збережено успішно.")
    except Exception as e:
        logging.error(f"Помилка збереження даних: {e}")

load()

# --- ЛОГІКА ФОРМАТУВАННЯ КОМБО ---
def format_combo(cards: list[str]) -> str:
    """Форматує список карток комбо в один рядок для Telegram."""
    if not cards or len(cards) < 3:
        # Якщо скрепер повернув повідомлення про помилку (як список з 3 рядків)
        if len(cards) == 3 and cards[0].startswith("Скрапер:"):
             return "\n".join(cards)
             
        return "\n".join(cards) if cards else DEFAULT_COMBO
        
    formatted = "✅ Щоденне комбо:\n"
    formatted += f"1️⃣: <b>{cards[0]}</b>\n"
    formatted += f"2️⃣: <b>{cards[1]}</b>\n"
    formatted += f"3️⃣: <b>{cards[2]}</b>"
    return formatted
# ----------------------------------


# === АВТООНОВЛЕННЯ (Scheduler) ===
async def fetch_and_update():
    """Виконує скрепінг у фоновому потоці та оновлює комбо."""
    global combo_text
        
    logging.info("Запуск scrape_for_combo у фоновому потоці...")
    
    # Запускаємо синхронну функцію скрепінгу в окремому потоці (для неблокування aiohttp)
    new_combo_list = await asyncio.to_thread(scrape_for_combo)
    
    if new_combo_list is None:
        logging.error("Скрепер повернув None. Комбо не оновлено.")
        return
        
    # Форматуємо отриманий список карток
    new_combo = format_combo(new_combo_list)
    
    if new_combo != combo_text: # Перевірка, чи комбо дійсно змінилося
        logging.info("Отримано нове комбо. Зберігаю.")
        combo_text = new_combo
        save()
        
        if ADMIN_ID and ADMIN_ID != 0:
            # Надсилаємо повідомлення адміністратору про успішне оновлення
            await bot.send_message(ADMIN_ID, "✅ Комбо оновлено автоматично скрепером!")
    else:
        logging.info("Комбо не змінилося або скрепер не знайшов валідне комбо.")


async def scheduler():
    """Планувальник, що запускає fetch регулярно."""
    await asyncio.sleep(30) # Затримка для коректного старту Webhook
    
    # Виконуємо перше оновлення, щоб отримати комбо одразу після старту
    await fetch_and_update()
    
    while True:
        # Чекаємо 3 години
        await asyncio.sleep(UPDATE_INTERVAL_SECONDS) 
        await fetch_and_update()

# Допоміжна функція для відображення адмін-панелі
async def render_admin_panel(message: types.Message):
    """Генерує та відправляє (або редагує) адмін-панель."""
    kb = [
        [types.InlineKeyboardButton(text="Оновити зараз (Scrape) 🔄", callback_data="force_scrape")],
        [types.InlineKeyboardButton(text="Головне меню 🏠", callback_data="start")]
    ]
    
    admin_text = (
        "<b>Панель адміністратора</b>\n\n"
        f"Поточне комбо:\n{combo_text}\n\n"
        f"Інтервал оновлення: {UPDATE_INTERVAL_SECONDS // 3600} годин.\n"
        "Для ручного комбо: <code>/setcombo &lt;Картка1&gt;, &lt;Картка2&gt;, &lt;Картка3&gt;</code>\n"
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

@dp.callback_query(F.data == "force_scrape")
async def force_scrape(c: types.CallbackQuery):
    """Обробник кнопки 'Оновити зараз'."""
    await c.answer("Запускаю скрепінг...")
    
    if c.from_user.id != ADMIN_ID: return
    
    # Виконуємо примусове оновлення
    await fetch_and_update()
    
    # Оновлюємо адмін-панель після завершення
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
            await m.answer("❌ Використання: <code>/setcombo &lt;Картка1&gt;, &lt;Картка2&gt;, &lt;Картка3&gt;</code>")
            return
            
        combo_input_text = combo_input[1].strip()
        card_list = [s.strip() for s in combo_input_text.split(',') if s.strip()]
        
        # Обробляємо випадок, коли користувач ввів три картки через кому
        if len(card_list) >= 3:
            combo_text = format_combo(card_list)
        else:
            # Якщо введений текст не схожий на список, зберігаємо як є
            combo_text = combo_input_text

        save()
        await m.answer(f"✅ Комбо встановлено вручну та збережено.\n")
    except Exception as e:
        logging.error(f"Помилка у setcombo: {e}")
        await m.answer("❌ Помилка при ручному встановленні комбо.")


# === Webhook Запуск ===

async def on_startup(app: web.Application):
    """Функція, яка викликається при старті aiohttp сервера."""
    try:
        # Встановлюємо Webhook
        await bot.set_webhook(WEBHOOK_URL)
        # Запускаємо планувальник скрепінгу у фоновому режимі
        asyncio.create_task(scheduler())
        logging.info(f"✅ БОТ УСПІШНО ЗАПУЩЕНО — РЕЖИМ WEBHOOK: {WEBHOOK_URL}")
    except TelegramUnauthorizedError:
        logging.critical("КРИТИЧНА ПОМИЛКА: Неправильний BOT_TOKEN!")
        await bot.session.close() 

app = web.Application()
app.on_startup.append(on_startup)
# Реєструємо хендлер для Webhook
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
