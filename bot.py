import asyncio
import logging
import os
import time 
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

# --- ІМПОРТ СКРАПЕРА ---
# MUST BE present in the same directory for the import to work.
import hamster_scraper 
# ------------------------

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Отримання змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Using str() ensures correct comparison
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
    # Reading current cards from the scraper's global variable
    cards = hamster_scraper.GLOBAL_COMBO_CARDS
    
    # 1. If hidden
    if not GLOBAL_COMBO_ACTIVE and not is_admin:
        return "❌ \\*Глобальна Активність: НЕАКТИВНО\\*\n\nКомбо тимчасово приховано адміністратором\\."
    
    # 2. If data is missing
    if not cards or len(cards) != 3:
        return "⚠️ \\*Комбо ще не встановлено\\!\\* Планувальник намагається знайти нові дані\\."

    # 3. If data is present (Active status)
    combo_date = time.strftime(r"%d\.%m\.%Y") # Escape dots for MarkdownV2
    # Format cards as a list of code (for fixed-width display)
    combo_list = "\n".join([f"• `{card}`" for card in cards])
    
    access_level = " (Адмін-Доступ)" if is_admin else ""
    
    return (
        f"✅ \\*Актуальне Комбо\\* {combo_date} {access_level}\n\n"
        f"👇 \\*\\*Картки, які потрібно прокачати:\\*\\*\n"
        f"{combo_list}\n\n"
        f"💰 \\*Отримайте мільйони монет за 3 правильні апгрейди\\!\\*"
    )

def get_start_message_text(user_id: int, is_admin: bool) -> str:
    """Формує текст вітального повідомлення."""
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
    exit(1)


# --- ХЕНДЛЕРИ КОМАНД ---

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    """Обробляє команду /start."""
    user_id = message.from_user.id
    is_admin = str(user_id) == ADMIN_ID
    
    text = get_start_message_text(user_id, is_admin)
    
    # FIX: Simplified syntax to prevent Pydantic ValidationError
    keyboard_rows = [
        [types.InlineKeyboardButton(text="Отримати комбо зараз ➡️", callback_data="get_combo")],
    ]
    
    if is_admin:
        keyboard_rows.append(
            [types.InlineKeyboardButton(text="Управління активацією ⚙️", callback_data="manage_activation")]
        )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await message.answer(text, reply_markup=keyboard)


# --- ХЕНДЛЕРИ АДМІН-ПАНЕЛІ ТА CALLBACKS ---

async def show_admin_panel(message: types.Message | types.CallbackQuery):
    """Відображає адміністративну панель."""
    if str(message.from_user.id) != ADMIN_ID:
        if isinstance(message, types.CallbackQuery):
            await message.answer("У вас немає доступу.", show_alert=True)
        else:
            await message.answer("У вас немає доступу до панелі адміністратора\\.")
        return

    text, btn_text, btn_callback = get_admin_panel_text()

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=btn_text, callback_data=btn_callback)],
            [types.InlineKeyboardButton(text="⬅️ Назад до /start", callback_data="back_to_start")],
        ]
    )
    
    target_message = message.message if isinstance(message, types.CallbackQuery) else message

    if isinstance(message, types.CallbackQuery):
        await target_message.edit_text(text, reply_markup=keyboard)
        await message.answer() # Dismiss the callback query
    else:
        await target_message.answer(text, reply_markup=keyboard)


@dp.callback_query(F.data.in_({"activate_combo", "deactivate_combo"}))
async def process_toggle_combo(callback: types.CallbackQuery):
    """Обробляє перемикання глобального статусу комбо."""
    global GLOBAL_COMBO_ACTIVE
    
    if str(callback.from_user.id) == ADMIN_ID:
        if callback.data == "activate_combo":
            GLOBAL_COMBO_ACTIVE = True
            alert_text = "Глобальне комбо АКТИВОВАНО"
        elif callback.data == "deactivate_combo":
            GLOBAL_COMBO_ACTIVE = False
            alert_text = "Глобальне комбо ДЕАКТИВОВАНО"
            
        await callback.answer(alert_text, show_alert=True)
        await show_admin_panel(callback)
    else:
        await callback.answer("Тільки адміністратор може керувати цим статусом\\.", show_alert=True)


@dp.callback_query(F.data == "get_combo")
async def process_get_combo(callback: types.CallbackQuery):
    """Обробляє натискання кнопки "Отримати комбо зараз"."""
    await callback.answer("Отримуємо актуальне комбо...", show_alert=False)
    
    user_id = callback.from_user.id
    is_admin = str(user_id) == ADMIN_ID
    
    combo_text = get_combo_text(is_admin)
    
    # Send the combo text (not editing the original message to avoid errors)
    await callback.message.answer(combo_text)


@dp.callback_query(F.data == "manage_activation")
async def process_manage_activation(callback: types.CallbackQuery):
    """Обробляє натискання "Управління активацією" (для Premium або Адмін-панелі)."""
    await callback.answer("Перехід до управління...", show_alert=False)

    if str(callback.from_user.id) == ADMIN_ID:
        await show_admin_panel(callback)
    else:
        # For regular users (Premium placeholder)
        await callback.message.answer("Тут буде панель управління активацією Premium \\(з Crypto Bot\\)\\.", parse_mode=ParseMode.MARKDOWN_V2)

@dp.callback_query(F.data == "back_to_start")
async def process_back_to_start(callback: types.CallbackQuery):
    """Повернення з панелі адміністратора до /start."""
    # Call the /start handler logic to update the message
    await command_start_handler(callback.message)
    await callback.answer() # Dismiss the callback query


# --- ФОНОВЕ ВИКОНАННЯ СКРАПЕРА (FIXED) ---

async def start_scheduler_task():
    """Запускає основну функцію скрапера у фоновому режимі (в окремому потоці)."""
    logger.info("Запуск планувальника скрапінгу у фоновому режимі...")
    try:
        # Calls the synchronous function in a separate thread
        await asyncio.to_thread(hamster_scraper.main_scheduler) 
    except AttributeError as e:
        logger.error(f"Критична помилка запуску скрапера: {e}. Переконайтеся, що hamster_scraper.py існує і містить main_scheduler().")
    except Exception as e:
        logger.error(f"Непередбачувана помилка в планувальнику: {e}")


async def main() -> None:
    """Головна функція запуску бота та планувальника."""
    logger.info("Бот запущено. Починаю отримувати оновлення...")

    # Start the scraper scheduler as a background task
    asyncio.create_task(start_scheduler_task())
    
    # Start bot polling
    await dp.start_polling(bot)
    
    logger.info("Бот зупинено.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Критична помилка при запуску програми: {e}")
