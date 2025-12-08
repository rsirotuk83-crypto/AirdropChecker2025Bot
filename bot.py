import os
import asyncio
import logging
import json
from datetime import datetime, timedelta

# --- КРИТИЧНО ВАЖЛИВИЙ ІМПОРТ ---
# Імпорт scraper-логіки та глобальної змінної для комбо
try:
    from hamster_scraper import main_scheduler, GLOBAL_COMBO_CARDS
except ImportError:
    # Запобігання падінню, якщо hamster_scraper.py не знайдено або має помилки
    logging.error("Не вдалося імпортувати main_scheduler та GLOBAL_COMBO_CARDS з hamster_scraper.py. Фонова робота не буде запущена.")
    GLOBAL_COMBO_CARDS = []
    def main_scheduler():
        logging.info("Фоновий планувальник-заглушка запущений. Скрапінг не працює.")
        return asyncio.sleep(3600)
# ---------------------------------

# Import necessary modules for Webhooks (aiohttp) and aiogram
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.exceptions import TelegramNetworkError, TelegramConflictError, TelegramBadRequest

# --- Налаштування логування ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Змінні оточення ---
# Обов'язкові змінні
BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")

# Webhook URL для Railway (автоматично надається)
# Використовуємо WEBHOOK_HOST, якщо він доступний, інакше припускаємо localhost для тестування
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = "/webhook"

# Формування WEBHOOK_URL. Якщо WEBHOOK_HOST є, використовуємо його, інакше - пустий рядок (що викличе помилку запуску Webhook)
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else ""

# Порт для aiohttp (беремо з PORT, якщо він є, інакше - 8080)
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
WEB_SERVER_HOST = "0.0.0.0"

# Перевірка ADMIN_ID
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (ValueError, TypeError):
    ADMIN_ID = None
    logging.warning("ПОПЕРЕДЖЕННЯ: ADMIN_ID не встановлено або некоректне. Адмін-функції вимкнено.")

# --- Ініціалізація даних ---
DATA_DIR = "/app/data"
DB_FILE = os.path.join(DATA_DIR, "db.json")

def load_data():
    """Завантажує дані активації з JSON файлу."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        logging.info(f"Створено директорію даних: {DATA_DIR}")
        
    if not os.path.exists(DB_FILE):
        logging.warning(f"Файл бази даних {DB_FILE} не знайдено. Створюю новий.")
        return {"users": {}, "combo_url": None} # Додано "combo_url" для потенційного використання

    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Забезпечення наявності необхідних ключів
            if "users" not in data:
                data["users"] = {}
            if "combo_url" not in data:
                data["combo_url"] = None
            return data
    except (json.JSONDecodeError, FileNotFoundError):
        logging.error("Помилка при завантаженні або парсингу db.json. Використовуються початкові значення.")
        return {"users": {}, "combo_url": None}

def save_data(data):
    """Зберігає дані активації в JSON файл."""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info("Дані успішно збережено.")
    except Exception as e:
        logging.error(f"Помилка при збереженні даних у db.json: {e}")

DB_DATA = load_data()

# --- Логіка активації ---
def is_user_premium_or_activated(user_id):
    """Перевіряє, чи є користувач преміум-користувачем або чи активовано його акаунт."""
    if user_id == ADMIN_ID:
        return True, "admin"
        
    if str(user_id) in DB_DATA["users"]:
        activation_date_str = DB_DATA["users"][str(user_id)].get("activated_until")
        if activation_date_str:
            try:
                activated_until = datetime.fromisoformat(activation_date_str)
                if activated_until > datetime.now():
                    return True, "activated"
            except ValueError:
                logging.error(f"Некоректний формат дати активації для користувача {user_id}")
    
    # Тут має бути логіка перевірки Telegram Premium
    return False, "not_activated"

# --- Клавіатури ---
def main_keyboard(user_id: int):
    """Основна клавіатура."""
    kb_content = [
        [InlineKeyboardButton(text="Отримати комбо 🔑", callback_data="get_combo_data")],
    ]
    if user_id == ADMIN_ID:
        kb_content.append([InlineKeyboardButton(text="Адмінка ⚙️", callback_data="admin_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=kb_content)

def admin_menu_keyboard():
    """Клавіатура для адміністратора."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Активувати Premium (7 днів)", callback_data="admin_activate_self")],
        [InlineKeyboardButton(text="Деактивувати Premium", callback_data="admin_deactivate_self")],
        [InlineKeyboardButton(text="Встановити URL комбо", callback_data="set_combo_url")],
        [InlineKeyboardButton(text="Поточний статус", callback_data="admin_status")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_start")]
    ])

# --- Хендлери ---

@CommandStart()
async def command_start_handler(message: Message):
    """Обробка команди /start."""
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "користувач"
    status, reason = is_user_premium_or_activated(user_id)
    
    text = f"Привіт, {first_name}!\n\n"
    text += f"Ваш Telegram ID: <code>{user_id}</code>\n"
    
    if status:
        text += f"✅ Ваш акаунт **{reason.upper()}**."
        kb = main_keyboard(user_id)
    else:
        text += "❌ Ваш акаунт не активовано. Комбо доступне лише для Premium-користувачів або після активації."
        # Використовуємо ту саму клавіатуру, але обробник get_combo_data відповість повідомленням про оплату
        kb = main_keyboard(user_id)
    
    await message.answer(text, reply_markup=kb)


@F.callback_query.data == "admin_menu"
async def admin_menu_handler(callback: CallbackQuery):
    """Відображення адмін-меню."""
    if callback.from_user.id == ADMIN_ID:
        combo_status = f"Актуальне Комбо: {', '.join(GLOBAL_COMBO_CARDS) if GLOBAL_COMBO_CARDS else 'НЕ ЗНАЙДЕНО'}"
        await callback.message.edit_text(
            f"Меню адміністратора:\n\n{combo_status}", 
            reply_markup=admin_menu_keyboard()
        )
    else:
        await callback.answer("У вас немає доступу до адмін-функцій.", show_alert=True)

# --- Адмін-функції (Управління активацією) ---
@F.callback_query.data == "admin_activate_self"
async def admin_activate_handler(callback: CallbackQuery):
    """Тимчасова активація комбо для тестування (Адмін)."""
    if callback.from_user.id == ADMIN_ID:
        user_id_to_activate = str(callback.from_user.id)
        activated_until = datetime.now() + timedelta(days=7) 
        
        DB_DATA["users"][user_id_to_activate] = {"activated_until": activated_until.isoformat()}
        save_data(DB_DATA)
        
        await callback.message.edit_text(
            f"Акаунт {user_id_to_activate} успішно активовано до {activated_until.strftime('%Y-%m-%d %H:%M')}",
            reply_markup=admin_menu_keyboard()
        )
    else:
        await callback.answer("Доступ заборонено.", show_alert=True)

@F.callback_query.data == "admin_deactivate_self"
async def admin_deactivate_handler(callback: CallbackQuery):
    """Тимчасова деактивація комбо для тестування (Адмін)."""
    if callback.from_user.id == ADMIN_ID:
        user_id_to_deactivate = str(callback.from_user.id)
        
        if user_id_to_deactivate in DB_DATA["users"]:
            del DB_DATA["users"][user_id_to_deactivate]
            save_data(DB_DATA)
            await callback.message.edit_text(
                f"Акаунт {user_id_to_deactivate} успішно деактивовано.",
                reply_markup=admin_menu_keyboard()
            )
        else:
            await callback.answer("Акаунт не знайдено в базі даних.", show_alert=True)
    else:
        await callback.answer("Доступ заборонено.", show_alert=True)

@F.callback_query.data == "admin_status"
async def admin_status_handler(callback: CallbackQuery):
    """Відображення поточного статусу системи."""
    if callback.from_user.id == ADMIN_ID:
        active_users = sum(1 for uid, data in DB_DATA["users"].items() 
                           if data.get("activated_until") and datetime.fromisoformat(data["activated_until"]) > datetime.now())
        
        combo_status = f"Актуальне Комбо: {', '.join(GLOBAL_COMBO_CARDS) if GLOBAL_COMBO_CARDS else 'НЕ ЗНАЙДЕНО (Скрапінг)'}"
        
        await callback.answer(
            f"Статус системи:\n\n"
            f"Активних Premium: {active_users}\n"
            f"{combo_status}\n"
            f"DB URL (legacy): {DB_DATA.get('combo_url')}",
            show_alert=True
        )
    await callback.answer()


@F.callback_query.data == "back_to_start"
async def back_to_start_handler(callback: CallbackQuery, bot: Bot):
    """Повернення до основного меню."""
    await command_start_handler(callback.message)
    await callback.answer()

# --- Логіка отримання комбо ---

@F.callback_query.data == "get_combo_data"
async def get_combo_data_handler(callback: CallbackQuery, bot: Bot):
    """Обробка запиту на отримання комбо."""
    user_id = callback.from_user.id
    status, reason = is_user_premium_or_activated(user_id)

    if status:
        if GLOBAL_COMBO_CARDS:
            combo_text = "✨ **СЬОГОДНІШНЄ КОМБО** ✨\n\n"
            combo_text += "• " + "\n• ".join(GLOBAL_COMBO_CARDS)
            combo_text += "\n\n_Дані отримано автоматично. Час оновлення: раз на 3 години._"
            
            await callback.message.edit_text(
                combo_text, 
                reply_markup=main_keyboard(user_id), # Повертаємо клавіатуру, якщо потрібно
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await callback.answer(
                "❌ Комбо ще не завантажено або скрапінг не спрацював. Спробуйте пізніше.",
                show_alert=True
            )
    else:
        # Логіка для неактивованих користувачів - пропозиція оплати
        await callback.answer(
            "Комбо доступне лише для активованих користувачів. Створення інвойсу (TBD).",
            show_alert=True
        )
        # TODO: Додати логіку Crypto Bot API для створення інвойсу тут

# --- Функції Webhook ---

async def on_startup(bot: Bot):
    """Встановлення Webhook та очищення старих оновлень при запуску."""
    if not BOT_TOKEN:
        logging.error("КРИТИЧНА ПОМИЛКА: BOT_TOKEN не встановлено.")
        exit(1)
    if not WEBHOOK_URL:
        logging.error("КРИТИЧНА ПОМИЛКА: WEBHOOK_HOST (або WEBHOOK_URL) не встановлено. Переконайтеся, що змінні Railway налаштовані.")
        exit(1)

    logging.info(f"Встановлення Webhook на: {WEBHOOK_URL}")
    try:
        # Встановлення Webhook
        await bot.set_webhook(
            url=WEBHOOK_URL, 
            drop_pending_updates=True
        )
        logging.info(f"WEBHOOK УСПІШНО ВСТАНОВЛЕНО та запущено на порту {WEB_SERVER_PORT}")
    except TelegramConflictError:
        logging.warning("TelegramConflictError: Webhook вже встановлено. Спроба видалення та перевизначення...")
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        logging.info("Webhook успішно перевизначено.")
    except Exception as e:
        logging.error(f"КРИТИЧНА ПОМИЛКА ПРИ НАЛАШТУВАННІ WEBHOOK: {e}")
        exit(1)


def register_handlers(dp: Dispatcher):
    """Реєстрація всіх хендлерів."""
    dp.message.register(command_start_handler, CommandStart())
    
    # Реєстрація загальних колбеків
    dp.callback_query.register(get_combo_data_handler, F.data == "get_combo_data")
    
    # Реєстрація адмін-колбеків
    dp.callback_query.register(admin_menu_handler, F.data == "admin_menu")
    dp.callback_query.register(admin_activate_handler, F.data == "admin_activate_self")
    dp.callback_query.register(admin_deactivate_handler, F.data == "admin_deactivate_self")
    dp.callback_query.register(admin_status_handler, F.data == "admin_status")
    dp.callback_query.register(back_to_start_handler, F.data == "back_to_start")


# --- Запуск ---
async def main():
    """Основна точка входу для Webhook-бота."""
    # Ініціалізація бота та диспетчера
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    register_handlers(dp)

    # 1. Запуск фонового планувальника скрапінгу
    try:
        logging.info("Запуск планувальника скрапінгу у фоновому режимі...")
        asyncio.create_task(main_scheduler())
    except Exception as e:
        # Це охоплює помилки, якщо main_scheduler не було імпортовано
        logging.error(f"Критична помилка запуску скрапера: {e}")

    # 2. Встановлення Webhook
    await on_startup(bot)

    # 3. Запуск aiohttp web-сервера для прийому оновлень
    app = web.Application()
    
    # Додавання обробника Telegram
    webhook_requests_handler = dp.get_web_app(bot=bot)
    app.router.add_post(WEBHOOK_PATH, webhook_requests_handler)
    
    # Запуск сервера
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)
    logging.info(f"БОТ УСПІШНО ЗАПУЩЕНО - Webhook слухає на {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
    await site.start()

    # Утримання `main` функції у робочому стані
    # Бот залишатиметься активним, очікуючи на завершення сайту aiohttp
    await asyncio.Event().wait()


if __name__ == '__main__':
    if not BOT_TOKEN:
        logging.error("КРИТИЧНА ПОМИЛКА: BOT_TOKEN не встановлено. Перевірте змінні оточення.")
    else:
        try:
            # Запуск асинхронної функції
            asyncio.run(main())
        except KeyboardInterrupt:
            logging.info("Бот зупинено вручну (KeyboardInterrupt).")
        except Exception as e:
            logging.error(f"Критична помилка виконання: {e}")
