import asyncio
import logging
import os
import time 
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

# --- ІМПОРТ СКРАПЕРА ---
# ВАЖЛИВО: Обидва файли (bot.py та hamster_scraper.py) мають бути в одній директорії.
import hamster_scraper 
# ------------------------

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Отримання змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Використовуємо str() для коректного порівняння ID
ADMIN_ID = str(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else "" 

# --- ГЛОБАЛЬНИЙ СТАТУС ДЛЯ УПРАВЛІННЯ АДМІНІСТРАТОРОМ ---
GLOBAL_COMBO_ACTIVE = True # Set to True by default
# --------------------------------------------------------


# --- ФУНКЦІЇ ДЛЯ БОТА ---

def create_bot_instance(token: str) -> Bot:
    """Створює екземпляр бота з властивостями за замовчуванням."""
    if not token:
        logger.critical("BOT_TOKEN не знайдено!")
        raise ValueError("BOT_TOKEN не встановлено.")

    default_properties = DefaultBotProperties(
        parse_mode=ParseMode.MARKDOWN_V2, 
        link_preview_is_disabled=True,    
        protect_content=False
    )
    return Bot(token=token, default=default_properties)

def get_combo_text(is_admin: bool) -> str:
    """Формує текст комбо на основі його статусу та знайдених карток."""
    
    # Читання даних з імпортованого модуля скрапера
    # Якщо тут виникає AttributeError, це 100% означає, що hamster_scraper.py — СТАРИЙ
    try:
        cards = hamster_scraper.GLOBAL_COMBO_CARDS
    except AttributeError:
        # Обробка помилки на випадок, якщо файл hamster_scraper.py старий
        logger.error("Критична помилка: Не знайдено hamster_scraper.GLOBAL_COMBO_CARDS. Перевірте файл скрапера.")
        return "❌ \\*Критична Помилка\\*\\! Змінна `GLOBAL_COMBO_CARDS` відсутня\\! Адміністратор: Оновіть файл `hamster_scraper\\.py`\\."


    # 1. If hidden
    if not GLOBAL_COMBO_ACTIVE and not is_admin:
        return "❌ \\*Глобальна Активність: НЕАКТИВНО\\*\n\nКомбо тимчасово приховано адміністратором\\."
    
    # 2. If data is missing (or scraper hasn't finished first run yet)
    if not cards or len(cards) != 3:
        # Show this message regardless of GLOBAL_COMBO_ACTIVE status
        return "⚠️ \\*Комбо ще не встановлено\\!\\* Планувальник намагається знайти нові дані\\."

    # 3. If data is present (Active status)
    # Форматуємо дату для MarkdownV2 (екрануємо крапки)
    combo_date = time.strftime(r"%d\.%m\.%Y") 
    # Форматуємо картки як список коду
    combo_list = "\n".join([f"• `{card}`" for card in cards])
    
    access_level = " (Адмін-Доступ)" if is_admin else ""
    
    # Escape symbols for MarkdownV2
    return (
        f"✅ \\*Актуальне Комбо\\* {combo_date} {access_level}\n\n"
        f"👇 \\*\\*Картки, які потрібно прокачати:\\*\\*\n"
        f"{combo_list}\n\n"
        f"💰 \\*Отримайте мільйони монет за 3 правильні апгрейди\\!\\*"
    )

def get_start_message_text(user_id: int, is_admin: bool) -> str:
    """Формує текст вітального повідомлення."""
    # Приклад умовної логіки для демонстрації
    status_text = "АКТИВОВАНО (Premium)" if user_id % 2 == 0 else "НЕАКТИВНО" 
    admin_status = "Адміністратор" if is_admin else "Користувач"
    global_status = "АКТИВНО ✅" if GLOBAL_COMBO_ACTIVE else "ДЕАКТИВОВАНО ❌"

    # Escape symbols for MarkdownV2
    return (
        f"👋 \\*Привіт\\!\\* \n\n"
        f"Ваш ID: `{user_id}`\n"
        f"Статус: \\*{admin_status}\\*\n"
        f"Статус Premium: \\*{status_text}\\*\n"
        f"Глобальна Активність: \\*{global_status}\\*\n\n"
        f"Цей бот надає ранній доступ до щоденних комбо та кодів для популярних криптоігор\\."
    )

def get_admin_panel_text() -> tuple:
    """Формує текст адміністративної панелі та дані для кнопок."""
    status_display = "АКТИВНО ✅" if GLOBAL_COMBO_ACTIVE else "ДЕАКТИВОВАНО ❌"
    button_text = "Деактивувати глобальне комбо ❌" if GLOBAL_COMBO_ACTIVE else "Активувати глобальне комбо ✅"
    button_callback = "deactivate_combo" if GLOBAL_COMBO_ACTIVE else "activate_combo"
    
    # Escape text for MarkdownV2
    text = (
        f"⚙️ \\*Панель адміністратора\\*\n\n"
        f"Поточний стан відображення комбо для всіх користувачів \\(Global Combo\\): \\*{status_display}\\*\n\n"
        f"Натисніть кнопку, щоб змінити стан\\."
    )
    return text, button_text, button_callback

# --- ІНІЦІАЛІЗАЦІЯ ---

try:
    bot = create_bot_instance(BOT_TOKEN)
    dp = Dispatcher()
except ValueError as e:
    logger.critical(e)
    # Якщо токен відсутній, програма має завершитися
    exit(1)


# --- ХЕНДЛЕРИ КОМАНД ---

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    """Обробляє команду /start."""
    user_id = message.from_user.id
    is_admin = str(user_id) == ADMIN_ID
    
    text = get_start_message_text(user_id, is_admin)
    
    # Створення клавіатури
    keyboard_rows = [
        [types.InlineKeyboardButton(text="Отримати комбо зараз ➡️", callback_data="get_combo")],
    ]
    
    if is_admin:
        keyboard_rows.append(
            [types.InlineKeyboardButton(text="Управління активацією ⚙️", callback_data="admin_panel")]
        )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    try:
        await message.answer(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        logger.error(f"Помилка відправки повідомлення /start: {e}")
        await message.answer("Помилка форматування. Будь ласка, спробуйте ще раз.")

@dp.message(Command("debug_scraper"))
async def command_debug_scraper_handler(message: types.Message) -> None:
    """(Тільки для адміністратора) Виводить вміст модуля hamster_scraper."""
    user_id = message.from_user.id
    if str(user_id) != ADMIN_ID:
        await message.reply("Доступ заборонено\\.")
        return
        
    # Отримуємо всі атрибути модуля
    attributes = dir(hamster_scraper)
    
    # Фільтруємо приватні атрибути та ті, які ми шукаємо
    relevant_attributes = [
        attr for attr in attributes if not attr.startswith('__') and 
        ('main_scheduler' in attr or 'GLOBAL_COMBO_CARDS' in attr or 'scrape' in attr)
    ]
    
    # Форматуємо висновок для MarkdownV2
    attributes_list = "\n".join([f"• `{attr}`" for attr in relevant_attributes])
    
    debug_text = (
        f"🔬 \\*Діагностика модуля `hamster_scraper`\\*\n\n"
        f"Шукані атрибути: `main_scheduler`, `GLOBAL_COMBO_CARDS`\\.\n\n"
        f"\\*Знайдені атрибути:\\*\n"
        f"{attributes_list}"
    )
    
    if 'main_scheduler' in relevant_attributes and 'GLOBAL_COMBO_CARDS' in relevant_attributes:
        debug_text += "\n\n✅ \\*ВИЯВЛЕНО УСПІХ\\*\\! Обидва критичні атрибути присутні\\."
    else:
        debug_text += "\n\n❌ \\*КРИТИЧНА НЕСПРАВНІСТЬ\\*\\! Один або обидва критичні атрибути відсутні\\."

    try:
        await message.answer(debug_text)
    except TelegramBadRequest as e:
        logger.error(f"Помилка відправки debug-повідомлення: {e}")
        await message.answer("Помилка форматування debug-повідомлення\\.")


# --- ХЕНДЛЕРИ CALLBACKS (КНОПКИ) ---

@dp.callback_query(F.data == "get_combo")
async def process_get_combo(callback_query: types.CallbackQuery, bot: Bot):
    """Обробляє натискання кнопки "Отримати комбо зараз"."""
    user_id = callback_query.from_user.id
    is_admin = str(user_id) == ADMIN_ID
    
    # Ця функція тепер містить try/except для AttributeError
    combo_text = get_combo_text(is_admin) 
    
    # Створюємо кнопку "Назад" або кнопку для адміністратора
    back_button = types.InlineKeyboardButton(text="⬅️ Назад до /start", callback_data="go_to_start")
    
    keyboard_rows = [[back_button]]
    
    if is_admin:
         keyboard_rows.insert(0, [types.InlineKeyboardButton(text="Оновити дані скрапера 🔄", callback_data="force_scrape")])

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=combo_text,
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        # Це нормально, якщо текст не змінився (наприклад, натиснули двічі швидко)
        logger.warning(f"TelegramBadRequest у process_get_combo: {e}")
    finally:
        await callback_query.answer()


@dp.callback_query(F.data == "admin_panel")
async def process_admin_panel(callback_query: types.CallbackQuery, bot: Bot):
    """Обробляє натискання кнопки "Управління активацією" (тільки для Admin)."""
    user_id = callback_query.from_user.id
    
    if str(user_id) != ADMIN_ID:
        await callback_query.answer("Доступ заборонено!")
        return
        
    text, button_text, button_callback = get_admin_panel_text()
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=button_text, callback_data=button_callback)],
        [types.InlineKeyboardButton(text="⬅️ Назад до /start", callback_data="go_to_start")]
    ])
    
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        logger.warning(f"TelegramBadRequest у process_admin_panel: {e}")
    finally:
        await callback_query.answer()


@dp.callback_query(F.data.in_({'activate_combo', 'deactivate_combo'}))
async def toggle_global_combo_status(callback_query: types.CallbackQuery, bot: Bot):
    """Перемикає глобальний статус відображення комбо."""
    global GLOBAL_COMBO_ACTIVE
    user_id = callback_query.from_user.id
    
    if str(user_id) != ADMIN_ID:
        await callback_query.answer("Доступ заборонено!")
        return
        
    # Зміна статусу
    if callback_query.data == 'activate_combo':
        GLOBAL_COMBO_ACTIVE = True
        logger.info(f"Адміністратор {user_id} АКТИВУВАВ глобальне комбо.")
        
    elif callback_query.data == 'deactivate_combo':
        GLOBAL_COMBO_ACTIVE = False
        logger.info(f"Адміністратор {user_id} ДЕАКТИВУВАВ глобальне комбо.")
    
    # Оновлення панелі адміністратора
    text, button_text, button_callback = get_admin_panel_text()
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=button_text, callback_data=button_callback)],
        [types.InlineKeyboardButton(text="⬅️ Назад до /start", callback_data="go_to_start")]
    ])
    
    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        logger.warning(f"TelegramBadRequest у toggle_global_combo_status: {e}")
    finally:
        await callback_query.answer(f"Статус оновлено: {'АКТИВНО' if GLOBAL_COMBO_ACTIVE else 'НЕАКТИВНО'}")


@dp.callback_query(F.data == "go_to_start")
async def process_go_to_start(callback_query: types.CallbackQuery, bot: Bot):
    """Обробляє повернення до початкового повідомлення /start."""
    user_id = callback_query.from_user.id
    is_admin = str(user_id) == ADMIN_ID
    
    text = get_start_message_text(user_id, is_admin)
    
    keyboard_rows = [
        [types.InlineKeyboardButton(text="Отримати комбо зараз ➡️", callback_data="get_combo")],
    ]
    if is_admin:
        keyboard_rows.append(
            [types.InlineKeyboardButton(text="Управління активацією ⚙️", callback_data="admin_panel")]
        )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    try:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        logger.warning(f"TelegramBadRequest у process_go_to_start: {e}")
    finally:
        await callback_query.answer()

@dp.callback_query(F.data == "force_scrape")
async def process_force_scrape(callback_query: types.CallbackQuery, bot: Bot):
    """Адміністративна функція: примусово запустити скрапінг."""
    user_id = callback_query.from_user.id
    
    if str(user_id) != ADMIN_ID:
        await callback_query.answer("Доступ заборонено!")
        return
        
    await callback_query.answer("Починаю примусовий скрапінг... Зачекайте 10-20 секунд.")
    
    try:
        # Спроба викликати потрібну функцію (якщо вона є)
        await asyncio.to_thread(hamster_scraper._scrape_for_combo)
        
        # Після скрапінгу оновлюємо повідомлення з новим комбо
        await process_get_combo(callback_query, bot)

    except AttributeError:
        # Якщо _scrape_for_combo не знайдено, це означає, що файл hamster_scraper.py — СТАРИЙ
        logger.error("Критична помилка: Не знайдено hamster_scraper._scrape_for_combo. Перевірте файл скрапера.")
        await bot.send_message(user_id, "❌ Критична помилка: Не вдалося запустити скрапінг. Файл `hamster_scraper.py` неактуальний.")
        
    except Exception as e:
        logger.error(f"Помилка примусового скрапінгу: {e}")
        await bot.send_message(user_id, "❌ Критична помилка під час скрапінгу. Дивіться логи.")
        

# --- ЗАПУСК ---

async def start_scheduler_task():
    """Запуск планувальника скрапінгу у фоновому режимі."""
    logger.info("Запуск планувальника скрапінгу у фоновому режимі...")
    try:
        # Виклик асинхронної функції main_scheduler з модуля hamster_scraper
        # Якщо тут виникає AttributeError, це 100% означає, що hamster_scraper.py — СТАРИЙ
        await hamster_scraper.main_scheduler()
    except AttributeError as e:
        logger.error(f"Критична помилка запуску скрапера: {e}. Переконайтеся, що hamster_scraper.py існує і містить main_scheduler().")
    except Exception as e:
        logger.error(f"Неочікувана помилка в планувальнику скрапінгу: {e}")

async def main() -> None:
    """Головна точка входу для запуску бота та планувальника."""
    
    # Створюємо фонове завдання для скрапера
    asyncio.create_task(start_scheduler_task())
    
    logger.info("Бот запущено. Починаю отримувати оновлення...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        # У Railway це викликається автоматично. Тут лише для локального тестування.
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот зупинено вручну.")
    except Exception as e:
        logger.critical(f"Критична помилка запуску: {e}")
