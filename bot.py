import os
import asyncio
import json
import logging
import httpx
from datetime import datetime
from aiohttp import web
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# --- Конфігурація ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Отримання змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", "8080"))

# КРИТИЧНА ПЕРЕВІРКА: WEBHOOK_HOST повинен бути HTTPS, наприклад: https://<domain>.up.railway.app
if not BOT_TOKEN or not WEBHOOK_HOST:
    raise RuntimeError("BOT_TOKEN або WEBHOOK_HOST (наприклад, https://<domain>.up.railway.app) не встановлено")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# --- Клас для безпечного зберігання даних (Асинхронна безпека) ---
class ComboStorage:
    DATA_PATH = Path("/app/data")
    DATA_FILE = DATA_PATH / "db.json"

    def __init__(self):
        self._combo_text = "Комбо ще не встановлено"
        self._source_url = ""
        self._lock = asyncio.Lock()
        self.load() # Синхронне первинне завантаження

    def load(self):
        """Синхронно завантажує дані при старті."""
        if self.DATA_FILE.exists():
            try:
                with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    self._combo_text = d.get("combo", self._combo_text)
                    self._source_url = d.get("url", "")
                    logger.info("Дані успішно завантажено з файлу.")
            except Exception as e:
                logger.warning(f"Помилка при читанні даних: {e}")

    async def save(self):
        """Асинхронно зберігає дані з використанням блокування."""
        async with self._lock:
            self.DATA_PATH.mkdir(parents=True, exist_ok=True)
            try:
                data = {"combo": self._combo_text, "url": self._source_url}
                with open(self.DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                logger.debug("Дані успішно збережено.")
            except Exception as e:
                logger.error(f"КРИТИЧНА ПОМИЛКА при збереженні даних: {e}")

    async def get_combo(self):
        async with self._lock:
            return self._combo_text

    async def set_combo(self, text: str):
        async with self._lock:
            self._combo_text = text
        await self.save()

    async def get_url(self):
        async with self._lock:
            return self._source_url

    async def set_url(self, url: str):
        async with self._lock:
            self._source_url = url
        await self.save()

# Ініціалізація сховища
storage = ComboStorage()
# Ініціалізація Bot та Dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === Асинхронне оновлення та планувальник ===

async def fetch_combo_data():
    """Асинхронно отримує дані з віддаленого URL."""
    source_url = await storage.get_url()
    if not source_url:
        logger.warning("URL для скрепінгу не встановлено.")
        return

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(source_url)
            r.raise_for_status() # Викликає виняток для 4xx/5xx відповідей
            
            new_combo_text = r.text.strip()
            current_combo_text = await storage.get_combo()

            if new_combo_text and new_combo_text != current_combo_text:
                await storage.set_combo(new_combo_text)
                logger.info("Комбо оновлено: дані відрізняються.")
                
                if ADMIN_ID:
                    try:
                        await bot.send_message(ADMIN_ID, "Комбо оновлено! Нові дані збережено.")
                    except Exception as e:
                        logger.error(f"Не вдалося відправити сповіщення адміністратору: {e}")
            else:
                logger.debug("Комбо не змінилося або отримано порожні дані.")

    except httpx.HTTPStatusError as e:
        logger.error(f"Помилка HTTP-статусу при отриманні даних: {e}")
    except httpx.RequestError as e:
        logger.error(f"Помилка запиту при отриманні даних: {e}")
    except Exception as e:
        logger.error(f"Непередбачувана помилка у fetch_combo_data: {e}")


async def scheduler():
    """Планувальник, який запускає оновлення щодня."""
    # Початкова затримка, щоб бот встиг повністю запуститися
    await asyncio.sleep(5) 
    logger.info("Планувальник запущено. Перше оновлення за 10 секунд.")
    
    # Виконуємо перше оновлення одразу після старту
    await asyncio.sleep(10)
    await fetch_combo_data() 
    
    while True:
        # Чекаємо 24 години
        await asyncio.sleep(86400) 
        await fetch_combo_data()


# === Хендлери (Використовують Async Storage) ===

@dp.message(CommandStart())
async def start_handler(m: types.Message):
    """Обробка команди /start."""
    kb = [[types.InlineKeyboardButton(text="Отримати комбо", callback_data="getcombo")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка", callback_data="admin_panel")])
    
    # Використовуємо .answer, що є більш універсальним
    await m.answer(
        "👋 *Привіт! Я ваш CryptoComboDaily бот.*\n\n"
        "Отримайте свіже комбо для Hamster Kombat та інших ігор.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode=ParseMode.MARKDOWN
    )

@dp.callback_query(F.data == "getcombo")
async def show_combo(c: types.CallbackQuery):
    """Показує актуальне комбо."""
    combo_text_data = await storage.get_combo()
    
    await c.message.edit_text(
        f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo_text_data}", 
        parse_mode="HTML"
    )
    await c.answer() # Завжди відповідаємо на CallbackQuery

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(c: types.CallbackQuery):
    """Панель адміністратора."""
    if c.from_user.id != ADMIN_ID:
        await c.answer("У вас немає доступу до цієї панелі.", show_alert=True)
        return
    
    current_url = await storage.get_url()
    
    await c.message.edit_text(
        f"<b>Адмінка</b>\n\nПоточний URL скрепінгу: <code>{current_url or 'Не встановлено'}</code>",
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Оновити зараз", callback_data="force_fetch")],
            [types.InlineKeyboardButton(text="Закрити", callback_data="close_admin")]
        ])
    )
    await c.answer()

@dp.callback_query(F.data == "force_fetch")
async def force_fetch(c: types.CallbackQuery):
    """Примусове оновлення даних."""
    if c.from_user.id != ADMIN_ID: return
    
    await c.answer("Запускаю примусове оновлення...", cache_time=5)
    await fetch_combo_data()
    
    # Оновлення тексту панелі після оновлення даних
    await c.message.edit_text("Оновлено! Перевірте дані командою /start.")

@dp.callback_query(F.data == "close_admin")
async def close_admin(c: types.CallbackQuery):
    """Закриває адмін-панель, повертаючи /start."""
    if c.from_user.id != ADMIN_ID: return
    
    await start_handler(c.message) # Повторно викликаємо хендлер /start для повернення
    await c.answer("Закрито.")


@dp.message(F.text.startswith("/seturl"))
async def seturl_handler(m: types.Message):
    """Встановлення нового URL для скрепінгу."""
    if m.from_user.id != ADMIN_ID: return
    
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        await m.answer("Використання: <code>/seturl https://example.com/api/combo</code>", parse_mode="HTML")
        return
    
    new_url = parts[1].strip()
    if not (new_url.startswith("http://") or new_url.startswith("https://")):
        await m.answer("URL повинен починатися з http:// або https://")
        return

    await storage.set_url(new_url)
    await m.answer(f"✅ URL збережено:\n<code>{new_url}</code>\nЗапускаю примусове оновлення.", parse_mode="HTML")
    await fetch_combo_data() # Одразу пробуємо завантажити дані

@dp.message(F.text.startswith("/setcombo"))
async def setcombo_handler(m: types.Message):
    """Ручне встановлення тексту комбо."""
    if m.from_user.id != ADMIN_ID: return
    
    new_combo = m.text.partition(" ")[2].strip() or "Порожнє"
    await storage.set_combo(new_combo)
    await m.answer("✅ Комбо збережено.")
    
# === Webhook Hooks та Запуск ===

async def on_startup(app: web.Application) -> None:
    """Виконується aiohttp при старті: встановлює Webhook та запускає планувальник."""
    
    # 1. Встановлення Webhook
    try:
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook встановлено: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Помилка при встановленні Webhook: {e}")
        
    # 2. Запуск фонового планувальника
    asyncio.create_task(scheduler())
    logger.info("Планувальник запущено як фонове завдання.")


async def on_shutdown(app: web.Application) -> None:
    """Виконується aiohttp при зупинці: видаляє Webhook."""
    logger.info("Видалення Webhook...")
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("Webhook видалено. Бот зупинено.")

# --- Ініціалізація aiohttp ---

app = web.Application()
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown) # Додаємо коректне видалення Webhook

# Реєстрація хендлера Telegram Webhook
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

if __name__ == "__main__":
    logger.info(f"Запуск сервера на 0.0.0.0:{PORT}")
    try:
        # Використовуємо web.run_app, як у вашому прикладі
        web.run_app(app, host="0.0.0.0", port=PORT)
    except RuntimeError:
        # Це типово для aiohttp в деяких середовищах
        logger.warning("RuntimeError перехоплено, aiohttp вже завершує роботу.")
    except Exception as e:
        logger.error(f"Критична помилка під час запуску web.run_app: {e}")
