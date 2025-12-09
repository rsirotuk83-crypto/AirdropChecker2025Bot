import os
import asyncio
import json
import logging
import httpx
from datetime import datetime
from aiohttp import web
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command 
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.exceptions import TelegramBadRequest

# --- Конфігурація ---
# Налаштовуємо логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Отримання змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN or not WEBHOOK_HOST:
    logger.error("КРИТИЧНА ПОМИЛКА: BOT_TOKEN або WEBHOOK_HOST не встановлено. Завершення.")
    exit(1)

# СТАБІЛЬНІСТЬ/БЕЗПЕКА: Додаємо токен в шлях webhook як секрет
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Ініціалізація бота та диспетчера з єдиним ParseMode=HTML
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- Утиліти для роботи з меню ---
def get_main_menu_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Генерує клавіатуру головного меню."""
    keyboard = [
        [types.InlineKeyboardButton(text="📦 Отримати комбо", callback_data="getcombo")]
    ]
    if user_id == ADMIN_ID:
        keyboard.append(
            [types.InlineKeyboardButton(text="⚙️ Адмінка", callback_data="admin_panel")]
        )
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

MAIN_MENU_TEXT = (
    "<b>👋 CryptoComboDaily</b>\n\n"
    "Отримайте актуальне комбо для Hamster Kombat та інших ігор."
)

# --- Асинхронний клас для безпечного зберігання даних ---
class ComboStorage:
    DATA_PATH = Path("/app/data")
    DATA_FILE = DATA_PATH / "db.json"

    def __init__(self):
        # Оновлений текст за замовчуванням
        self._combo_text = "Комбо ще не встановлено. Використовуйте /setcombo або /seturl (для адміністратора)."
        self._source_url = ""
        self._lock = asyncio.Lock()
        self.load() 

    def load(self):
        """Синхронно завантажує дані при старті."""
        if self.DATA_FILE.exists():
            try:
                with open(self.DATA_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    self._combo_text = d.get("combo", self._combo_text)
                    self._source_url = d.get("url", "")
                    logger.info(f"Сховище: Дані успішно завантажено. URL: {self._source_url[:30]}...")
            except Exception as e:
                logger.warning(f"Сховище: Помилка при читанні даних: {e}")

    async def save(self):
        """Асинхронно зберігає дані з використанням блокування."""
        async with self._lock:
            self.DATA_PATH.mkdir(parents=True, exist_ok=True)
            try:
                data = {"combo": self._combo_text, "url": self._source_url}
                # Використовуємо run_in_executor для блокуючого I/O
                await asyncio.to_thread(self._sync_save, data)
                logger.debug("Сховище: Дані успішно збережено.")
            except Exception as e:
                logger.error(f"Сховище: КРИТИЧНА ПОМИЛКА при збереженні даних: {e}")

    def _sync_save(self, data):
        """Синхронний запис для використання в to_thread."""
        with open(self.DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)

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

storage = ComboStorage()


# === Асинхронне оновлення та планувальник ===

async def fetch_combo_data():
    """Асинхронно отримує дані з віддаленого URL."""
    source_url = await storage.get_url()
    if not source_url:
        logger.warning("Скрепінг: URL для скрепінгу не встановлено. Пропускаю оновлення.")
        return

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(source_url)
            r.raise_for_status() 
            
            new_combo_text = r.text.strip()
            current_combo_text = await storage.get_combo()

            if new_combo_text and new_combo_text != current_combo_text:
                await storage.set_combo(new_combo_text)
                logger.info("Скрепінг: Комбо оновлено: дані відрізняються.")
                
                if ADMIN_ID:
                    try:
                        # Відправлення сповіщення адміністратору
                        await bot.send_message(ADMIN_ID, "✅ Комбо оновлено! Нові дані збережено.")
                    except Exception as e:
                        logger.error(f"Скрепінг: Не вдалося відправити сповіщення адміністратору: {e}")
            else:
                logger.debug("Скрепінг: Комбо не змінилося або отримано порожні дані.")

    except httpx.HTTPStatusError as e:
        logger.error(f"Скрепінг: Помилка HTTP-статусу: {e}")
    except httpx.RequestError as e:
        logger.error(f"Скрепінг: Помилка запиту: {e}")
    except Exception as e:
        logger.error(f"Скрепінг: Непередбачувана помилка: {e}")


async def scheduler():
    """Планувальник, який запускає оновлення."""
    await asyncio.sleep(5) 
    logger.info("Планувальник запущено. Перше оновлення за 30 секунд.")
    
    await asyncio.sleep(30)
    await fetch_combo_data() 
    
    while True:
        await asyncio.sleep(86400) # 24 години
        await fetch_combo_data()


# === Хендлери ===

@dp.message(CommandStart())
async def start_handler(m: types.Message):
    """
    ОБРОБКА /START: Надсилає НОВЕ повідомлення з головним меню.
    """
    logger.info(f"ХЕНДЛЕР: Отримано команду /start від user={m.from_user.id}")
    
    await m.answer(
        MAIN_MENU_TEXT,
        reply_markup=get_main_menu_keyboard(m.from_user.id)
    )

@dp.message(Command("start_info"))
async def start_info_handler(m: types.Message):
    """Додаткова інформація для адміна про налаштування."""
    if m.from_user.id != ADMIN_ID:
        await m.answer("Ця команда лише для адміністратора.")
        return

    current_url = await storage.get_url()
    
    message_text = "⚙️ <b>НАЛАШТУВАННЯ БОТА</b>\n\n"
    message_text += "1. <b>URL скрепінгу:</b> "
    
    if not current_url:
        message_text += "🔴 <b>Не встановлено</b>.\n\n"
        message_text += "Будь ласка, встановіть його командою:\n"
        message_text += "<code>/seturl https://ваш-джерело.com/combo.txt</code>\n\n"
        message_text += "2. <b>Ручне комбо:</b> Ви можете встановити комбо вручну:\n"
        message_text += "<code>/setcombo Нове комбо</code>"
    else:
        message_text += f"✅ <code>{current_url}</code>\n\n"
        message_text += "2. <b>Примусове оновлення:</b> Використовуйте кнопку в Адмінці."
        
    await m.answer(message_text)


@dp.callback_query(F.data == "getcombo")
async def show_combo(c: types.CallbackQuery):
    """Показує актуальне комбо."""
    combo_text_data = await storage.get_combo()
    
    await c.message.edit_text(
        f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo_text_data}", 
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="<< Назад", callback_data="back_to_start")]
        ])
    )
    await c.answer() 

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("У вас немає доступу до цієї панелі.", show_alert=True)
        return
    
    current_url = await storage.get_url()
    
    await c.message.edit_text(
        f"<b>Адмінка</b>\n\nПоточний URL скрепінгу: <code>{current_url or 'Не встановлено'}</code>\n\n"
        f"Використовуйте команду <code>/seturl</code> або <code>/setcombo</code> для зміни налаштувань.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Оновити зараз", callback_data="force_fetch")],
            [types.InlineKeyboardButton(text="<< Назад", callback_data="back_to_start")] 
        ])
    )
    await c.answer()

@dp.callback_query(F.data == "force_fetch")
async def force_fetch(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    
    current_url = await storage.get_url()
    if not current_url:
        await c.answer("Не вдалося оновити. URL скрепінгу не встановлено.", show_alert=True)
        return
    
    await c.answer("Запускаю примусове оновлення...", cache_time=5)
    await fetch_combo_data()
    
    await c.message.edit_text(
        f"✅ Оновлено!\n"
        f"Перевірка завершена. Якщо дані змінилися, вони вже збережені.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="<< Назад", callback_data="back_to_start")] 
        ])
    )

@dp.callback_query(F.data == "back_to_start")
async def back_to_start_handler(c: types.CallbackQuery):
    """
    ОБРОБКА КНОПКИ 'НАЗАД': Редагує поточне повідомлення на головне меню.
    """
    logger.info(f"ХЕНДЛЕР: Отримано запит back_to_start від user={c.from_user.id}. Редагую повідомлення.")
    
    # Використовуємо MAIN_MENU_TEXT та get_main_menu_keyboard
    await c.message.edit_text(
        MAIN_MENU_TEXT,
        reply_markup=get_main_menu_keyboard(c.from_user.id)
    )
    await c.answer("Головне меню.")

@dp.message(F.text.startswith("/seturl"))
async def seturl_handler(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        await m.answer("❌ Використання: <code>/seturl https://example.com/api/combo.txt</code>")
        return
    
    new_url = parts[1].strip()
    if not (new_url.startswith("http://") or new_url.startswith("https://")):
        await m.answer("❌ URL повинен починатися з http:// або https://")
        return

    await storage.set_url(new_url)
    await m.answer(f"✅ URL збережено:\n<code>{new_url}</code>\n\nЗапускаю примусове оновлення. Перевірте логі!")
    await fetch_combo_data() 

@dp.message(F.text.startswith("/setcombo"))
async def setcombo_handler(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    
    new_combo = m.text.partition(" ")[2].strip() or "Порожнє"
    await storage.set_combo(new_combo)
    await m.answer("✅ Комбо збережено.")

# --- Webhook Hooks та Запуск ---

async def set_webhook_and_clear_updates():
    """Встановлює Webhook і очищає чергу старих оновлень."""
    try:
        # Очищаємо старі вебхуки та pending updates
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook очищено від старих оновлень.")
        
        # Встановлюємо webhook на URL з токеном у шляху 
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook встановлено: {WEBHOOK_URL}")
    except TelegramBadRequest as e:
        logger.error(f"Помилка Telegram при встановленні Webhook: {e}")
    except Exception as e:
        logger.error(f"Непередбачувана помилка при встановленні Webhook: {e}")


async def on_startup(app: web.Application) -> None:
    """Виконується aiohttp при старті: встановлює Webhook та запускає планувальник."""
    await set_webhook_and_clear_updates()
    
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
app.on_shutdown.append(on_shutdown) 

# SimpleRequestHandler реєструємо на шляху з токеном 
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

if __name__ == "__main__":
    logger.info(f"Запуск сервера на 0.0.0.0:{PORT}")
    try:
        web.run_app(app, host="0.0.0.0", port=PORT)
    except Exception as e:
        logger.error(f"Критична помилка під час запуску web.run_app: {e}")
