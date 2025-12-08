import os
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, List

# --- КРИТИЧНО ВАЖЛИВИЙ ІМПОРТ ДЛЯ СКРАПЕРА ---
try:
    # Припускаємо, що hamster_scraper.py знаходиться у тому ж каталозі
    from hamster_scraper import main_scheduler, GLOBAL_COMBO_CARDS
except ImportError as e:
    logging.error(f"Не вдалося імпортувати модуль скрапера: {e}. Переконайтеся, що hamster_scraper.py існує.")
    # Якщо імпорт не вдався, заглушка, щоб код працював
    GLOBAL_COMBO_CARDS: List[str] = []
    def main_scheduler():
        logging.warning("Фоновий планувальник не запущений, оскільки скрапер не імпортується.")
        return asyncio.sleep(3600) # Чекаємо годину

# --- ІМПОРТИ AIOGRAM ТА WEBHOOK ---
import aiohttp.web
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramConflictError # Додано ConflictError

# --- КОНСТАНТИ ТА ЗМІННІ СЕРЕДОВИЩА ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Змінні оточення
BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")

ADMIN_ID_RAW = os.getenv("ADMIN_ID")
ADMIN_ID: int = 0
try:
    ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW else 0
except (ValueError, TypeError):
    logging.error("ADMIN_ID не встановлено або некоректне. Адмін-функції вимкнено.")

# Конфігурація Webhook
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = "/webhook"
# WEBHOOK_URL буде виглядати як: https://airdropchecker2025bot-production.up.railway.app/webhook
WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else ""
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.environ.get("PORT", 8080))

# Файл даних для збереження стану
DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "db.json")

# --- МОДЕЛЬ ДАНИХ (БАЗА ДАНИХ) ---

class BotDB:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.data: Dict[str, Any] = {
            "premium_users": {},  # {user_id: datetime_str (end date)}
            "global_combo": None, # [card1, card2, card3]
            "global_access": False, # Чи дозволено доступ усім
            "crypto_bot_token": CRYPTO_BOT_TOKEN # Токен для Crypto Bot API
        }
        self._load()

    def _load(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        logging.info(f"Перевірено або створено директорію даних: {DATA_DIR}")
        
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    self.data = json.load(f)
                logging.info("Дані успішно завантажено.")
            except (IOError, json.JSONDecodeError):
                logging.warning(f"Помилка читання або парсингу файлу бази даних {self.db_file}. Створено новий.")
                self._save()
        else:
            logging.warning(f"Файл бази даних {self.db_file} не знайдено. Будуть використані початкові значення.")
            self._save()

        # Забезпечуємо, що адмін завжди має преміум
        if ADMIN_ID and str(ADMIN_ID) not in self.data["premium_users"]:
            # Встановлюємо дату закінчення через 100 років для адміна
            self.data["premium_users"][str(ADMIN_ID)] = (datetime.now().replace(year=datetime.now().year + 100)).isoformat()
            logging.info(f"Адмін ID {ADMIN_ID} додано до Premium.")
            self._save()
        
    def _save(self):
        try:
            with open(self.db_file, 'w') as f:
                json.dump(self.data, f, indent=4)
            logging.info("Дані успішно збережено.")
        except IOError as e:
            logging.error(f"КРИТИЧНА ПОМИЛКА: Не вдалося зберегти дані у файл {self.db_file}: {e}")

    def is_premium(self, user_id: int) -> bool:
        user_id_str = str(user_id)
        if user_id_str == str(ADMIN_ID):
            return True
        
        if self.data["global_access"]:
            return True

        if user_id_str in self.data["premium_users"]:
            expiry_date_str = self.data["premium_users"][user_id_str]
            if expiry_date_str:
                expiry_date = datetime.fromisoformat(expiry_date_str)
                return datetime.now() < expiry_date
        return False
    
    # ... інші методи (set_combo, set_global_access, add_premium, etc.)
    # Прості методи для демонстрації
    def set_global_combo(self, combo: List[str]):
        self.data["global_combo"] = combo
        self._save()

    def get_global_combo(self) -> List[str] | None:
        return self.data["global_combo"]
    
    def set_global_access(self, status: bool):
        self.data["global_access"] = status
        self._save()
        
    def get_global_access(self) -> bool:
        return self.data["global_access"]

# Ініціалізація бази даних
db = BotDB(DB_FILE)

# --- ІНІЦІАЛІЗАЦІЯ БОТА ---
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.MARKDOWN_V2)
dp = Dispatcher()

# --- ОБРОБНИКИ КОМАНД ТА КНОПОК ---

def get_main_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Отримати комбо 🔑", callback_data="get_combo")],
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton(text="Адмінка ⚙️", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    
    await message.answer(
        f"Привіт, {message.from_user.full_name}\\!\n\nВаш ID: `{user_id}`\n\nНатисніть кнопку:",
        reply_markup=get_main_keyboard(is_admin)
    )

async def admin_panel(c: CallbackQuery | Message) -> None:
    if isinstance(c, CallbackQuery):
        user_id = c.from_user.id
    elif isinstance(c, Message):
        user_id = c.from_user.id
    else:
        return

    if user_id != ADMIN_ID:
        if isinstance(c, CallbackQuery):
            await c.answer("Ви не адміністратор!", show_alert=True)
        return

    # Перевіряємо, що скрапер оновив комбо
    current_combo_list = db.get_global_combo() if db.get_global_combo() else GLOBAL_COMBO_CARDS
    combo_status = "\\n\\- " + "\\n\\- ".join(current_combo_list) if current_combo_list else "❌ Комбо не встановлено"

    global_access_status = "✅ УВІМКНЕНО" if db.get_global_access() else "❌ ВИМКНЕНО"
    
    premium_users_count = len(db.data["premium_users"])

    text = (
        "*⚙️ Панель адміністратора*\n\n"
        f"*Статус Комбо:*\n{combo_status}\n\n"
        f"*Глобальний доступ: {global_access_status}*\n"
        f"*Premium користувачів:* {premium_users_count}\n\n"
        "Для встановлення комбо вручну скористайтеся `/setcombo <картка1>|<картка2>|<картка3>`"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Оновити комбо зараз (Скрапер)", callback_data="force_fetch")],
        [InlineKeyboardButton(text=f"Глобальний доступ: {global_access_status}", callback_data="toggle_global")],
        [InlineKeyboardButton(text=f"Управління Premium ({premium_users_count} users)", callback_data="premium_manage")],
        [InlineKeyboardButton(text="⬅️ Головне меню", callback_data="main_menu")]
    ])
    
    if isinstance(c, CallbackQuery):
        try:
            await c.message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN_V2)
            await c.answer()
        except TelegramBadRequest:
            # Ігноруємо, якщо повідомлення не змінилося
            await c.answer("Панель не змінилася.")
    elif isinstance(c, Message):
        await c.answer(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN_V2)


@dp.callback_query(lambda c: c.data == "admin_panel")
async def process_admin_panel(c: CallbackQuery):
    await admin_panel(c)

@dp.callback_query(lambda c: c.data == "main_menu")
async def process_main_menu(c: CallbackQuery):
    user_id = c.from_user.id
    is_admin = user_id == ADMIN_ID
    await c.message.edit_text(
        f"Привіт, {c.from_user.full_name}\\!\n\nВаш ID: `{user_id}`\n\nНатисніть кнопку:",
        reply_markup=get_main_keyboard(is_admin)
    )
    await c.answer()

@dp.callback_query(lambda c: c.data == "toggle_global")
async def toggle_global_access(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Ви не адміністратор!", show_alert=True)
    
    new_status = not db.get_global_access()
    db.set_global_access(new_status)
    await admin_panel(c)
    await c.answer(f"Глобальний доступ {'УВІМКНЕНО' if new_status else 'ВИМКНЕНО'}")


@dp.callback_query(lambda c: c.data == "force_fetch")
async def force_fetch_combo(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Ви не адміністратор!", show_alert=True)
    
    await c.answer("Запускаю скрапер...")
    
    # Виклик синхронного скрапінгу в окремому потоці, щоб не блокувати AIOHTTP
    from hamster_scraper import _scrape_for_combo
    
    new_combo = await asyncio.to_thread(_scrape_for_combo) 
    
    if new_combo:
        # Оновлюємо глобальну змінну, яку планувальник оновлює регулярно
        from hamster_scraper import GLOBAL_COMBO_CARDS as G
        G[:] = new_combo 
        
        # Оновлюємо базу даних, щоб відобразити нове комбо
        db.set_global_combo(new_combo)
        await admin_panel(c)
        await c.answer("Комбо успішно оновлено!")
    else:
        await c.answer("Помилка скрапінгу. Перевірте логі!")


@dp.message(Command("setcombo"))
async def set_combo_manual(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Ця команда доступна лише адміністратору.")
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer(
            "❌ Використання: `/setcombo <картка1>|<картка2>|<картка3>`", 
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    combo_text = args[1].strip()
    combo_list = [c.strip() for c in combo_text.split('|') if c.strip()]
    
    if len(combo_list) != 3:
        return await message.answer("❌ Комбо має містити рівно три картки, розділені символом `|`.")
        
    db.set_global_combo(combo_list)
    
    # Також оновлюємо глобальну змінну скрапера для синхронізації
    try:
        from hamster_scraper import GLOBAL_COMBO_CARDS as G
        G[:] = combo_list
    except ImportError:
        logging.warning("Не вдалося оновити глобальну змінну скрапера. Перевірте імпорт.")
        
    await message.answer(
        f"✅ Комбо успішно встановлено вручну на:\n\\- {combo_list[0]}\n\\- {combo_list[1]}\n\\- {combo_list[2]}",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    await admin_panel(message)


@dp.callback_query(lambda c: c.data == "get_combo")
async def get_combo_data_handler(c: CallbackQuery):
    user_id = c.from_user.id
    
    if not db.is_premium(user_id):
        # Якщо користувач не premium і не адмін
        # Тут має бути логіка генерації інвойсу, але для простоти...
        await c.answer("Комбо доступне лише для преміум-користувачів.", show_alert=True)
        # Додайте тут кнопку для оплати, якщо потрібно
        return

    # --- ВИКОРИСТАННЯ ГЛОБАЛЬНОЇ ЗМІННОЇ З СКРАПЕРА ---
    combo_list = db.get_global_combo()
    
    # Якщо скрапер не встиг завантажити, але є дані з бази
    if not combo_list and GLOBAL_COMBO_CARDS:
        combo_list = GLOBAL_COMBO_CARDS
        db.set_global_combo(combo_list) # Зберігаємо у базу, якщо отримали вперше
    
    # Фінальна перевірка
    if not combo_list:
        await c.answer("Комбо ще не встановлено. Адміністратор має його встановити.", show_alert=True)
        return
        
    combo_text = "\\n\\- ".join(combo_list)
    date_str = datetime.now().strftime("%d\\.%m\\.%Y")
    
    message_text = (
        f"🏆 *Щоденне комбо на {date_str}* 🏆\n\n"
        f"Отримайте *5,000,000* монет, купивши:\n"
        f"\\- {combo_text}\n\n"
        "_(Дані оновлюються автоматично кожні 3 години\.)_"
    )
    
    await c.message.answer(
        message_text,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    await c.answer()

# --- ФУНКЦІЇ ЗАПУСКУ WEBHOOK ---

async def on_startup(bot: Bot) -> None:
    """Викликається перед запуском Webhook."""
    if not WEBHOOK_HOST:
        logging.error("WEBHOOK_HOST не встановлено. Бот не може запуститися через Webhook.")
        return
    
    # 1. Спроба видалити старий Webhook (якщо був Polling)
    try:
        await bot.delete_webhook()
        logging.info("Спроба видалення старого Webhook та очищення оновлень...")
    except TelegramConflictError:
        # Ігноруємо, якщо Webhook не було
        pass

    # 2. Встановлення нового Webhook
    try:
        await bot.set_webhook(WEBHOOK_URL)
        logging.info(f"WEBHOOK УСПІШНО ВСТАНОВЛЕНО на: {WEBHOOK_URL}")
    except Exception as e:
        logging.error(f"Помилка встановлення Webhook на {WEBHOOK_URL}: {e}")
        raise

    # 3. Запуск фонового планувальника скрапінгу
    logging.info("Запуск планувальника скрапінгу у фоновому режимі...")
    asyncio.create_task(main_scheduler())


async def on_shutdown(bot: Bot) -> None:
    """Викликається при вимкненні Webhook."""
    logging.warning("Сервер вимикається. Видаляю Webhook...")
    await bot.delete_webhook()

def main() -> None:
    """Головна функція для запуску Webhook-сервера."""
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN не знайдено в змінних оточення. Неможливо запустити бот.")
        return
    
    # Налаштування диспетчера
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Налаштування Webhook-застосунку
    app = aiohttp.web.Application()
    
    # Підключення диспетчера як обробника POST-запитів на WEBHOOK_PATH
    webhook_requests_handler = dp.get_web_app_factory()
    app.router.add_post(WEBHOOK_PATH, webhook_requests_handler)
    
    # Запуск сервера
    logging.info(f"БОТ УСПІШНО ЗАПУЩЕНО - Webhook слухає на {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
    aiohttp.web.run_app(
        app, 
        host=WEB_SERVER_HOST, 
        port=WEB_SERVER_PORT
    )

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Критична помилка запуску бота: {e}")
