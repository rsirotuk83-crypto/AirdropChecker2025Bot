import asyncio
import logging
import os
import time 
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

# --- ІМПОРТ СКРАПЕРА ---
# Цей модуль містить GLOBAL_COMBO_CARDS та функцію main_scheduler()
import hamster_scraper 
# ------------------------

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Отримання змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID") 

# --- ГЛОБАЛЬНИЙ СТАТУС ДЛЯ УПРАВЛІННЯ АДМІНІСТРАТОРОМ ---
# Ця змінна керує відображенням комбо для звичайних користувачів
GLOBAL_COMBO_ACTIVE = False
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
    # Звертаємося до глобальної змінної з модуля скрапера
    cards = hamster_scraper.GLOBAL_COMBO_CARDS
    
    # Перевірка, чи активне відображення (встановлене адміном)
    if not GLOBAL_COMBO_ACTIVE and not is_admin:
        return "❌ *Глобальна Активність: НЕАКТИВНО*\n\nКомбо тимчасово приховано адміністратором\\."
    
    # Перевірка наявності даних
    if cards and len(cards) == 3:
        combo_date = time.strftime("%d\\.%m\\.%Y")
        # Форматуємо картки у вигляді списку коду
        combo_list = "\n".join([f"• `{card}`" for card in cards])
        
        access_level = " (Повний Доступ)" if is_admin else " (Premium)"
        
        return (
            f"✅ *Актуальне Комбо* {combo_date} {access_level}\n\n"
            f"👇 **Картки, які потрібно прокачати:**\n"
            f"{combo_list}\n\n"
            f"💰 *Отримайте мільйони монет за 3 правильні апгрейди\\!*"
        )
    else:
        # Комбо активне, але скрапер ще не знайшов дані
        return "⚠️ *Комбо ще не встановлено\\!* Планувальник намагається знайти нові дані\\."

def get_start_message_text(user_id: int, is_admin: bool) -> str:
    """Формує текст вітального повідомлення."""
    # Фіктивний статус Premium для прикладу
    status_text = "АКТИВОВАНО" if user_id % 2 == 0 else "НЕАКТИВНО" 
    admin_status = "Адміністратор" if is_admin else "Користувач"
    global_status = "АКТИВНО" if GLOBAL_COMBO_ACTIVE else "НЕАКТИВНО"

    # Екрануємо символи для MarkdownV2
    return (
        f"👋 *Привіт\\!* \n\n"
        f"Ваш ID: `{user_id}`\n"
        f"Статус: *{admin_status}*\n"
        f"Статус Premium: *{status_text}*\n"
        f"Глобальна Активність: *{global_status}*\n\n"
        f"Цей бот надає ранній доступ до щоденних комбо та кодів для популярних криптоігор\\."
    )

def get_admin_panel_text() -> tuple:
    """Формує текст адміністративної панелі та дані для кнопок."""
    status_display = "АКТИВНО ✅" if GLOBAL_COMBO_ACTIVE else "ДЕАКТИВОВАНО ❌"
    button_text = "Деактивувати глобальне комбо ❌" if GLOBAL_COMBO_ACTIVE else "Активувати глобальне комбо ✅"
    button_callback = "deactivate_combo" if GLOBAL_COMBO_ACTIVE else "activate_combo"
    
    text = (
        f"⚙️ *Панель адміністратора*\n\n"
        f"Поточний стан відображення комбо для всіх користувачів \\(Global Combo\\): *{status_display}*\n\n"
        f"Натисніть кнопку, щоб змінити стан\\."
    )
    return text, button_text, button_callback

# --- ІНІЦІАЛІЗАЦІЯ ---

bot = create_bot_instance(BOT_TOKEN)
dp = Dispatcher()

# --- ХЕНДЛЕРИ КОМАНД ---

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    """Обробляє команду /start."""
    user_id = message.from_user.id
    is_admin = str(user_id) == ADMIN_ID
    
    text = get_start_message_text(user_id, is_admin)
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Отримати комбо зараз ➡️", callback_data="get_combo")],
            # Додаємо кнопку управління активацією тільки для адміністратора
            *([types.InlineKeyboardButton(text="Управління активацією ⚙️", callback_data="manage_activation")] if is_admin else []),
        ]
    )

    await message.answer(text, reply_markup=keyboard)


# --- ХЕНДЛЕРИ АДМІН-ПАНЕЛІ ---

@dp.message(F.text.lower().in_({"/admin", "/activate"}))
async def command_admin(message: types.Message):
    """Обробляє команди /admin та /activate."""
    if str(message.from_user.id) == ADMIN_ID:
        await show_admin_panel(message)
    else:
        await message.answer("У вас немає доступу до панелі адміністратора\\.")

async def show_admin_panel(message: types.Message | types.CallbackQuery):
    """Відображає адміністративну панель."""
    text, btn_text, btn_callback = get_admin_panel_text()

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=btn_text, callback_data=btn_callback)],
            [types.InlineKeyboardButton(text="⬅️ Назад до /start", callback_data="back_to_start")],
        ]
    )
    
    # Використовуємо .message для CallbackQuery
    target_message = message.message if isinstance(message, types.CallbackQuery) else message

    await target_message.answer(text, reply_markup=keyboard)


@dp.callback_query(F.data.in_({"activate_combo", "deactivate_combo"}))
async def process_toggle_combo(callback: types.CallbackQuery):
    """Обробляє перемикання глобального статусу комбо."""
    global GLOBAL_COMBO_ACTIVE
    
    if str(callback.from_user.id) == ADMIN_ID:
        
        if callback.data == "activate_combo":
            GLOBAL_COMBO_ACTIVE = True
            await callback.answer("Глобальне комбо АКТИВОВАНО", show_alert=True)
        elif callback.data == "deactivate_combo":
            GLOBAL_COMBO_ACTIVE = False
            await callback.answer("Глобальне комбо ДЕАКТИВОВАНО", show_alert=True)
            
        # Оновлюємо адмін-панель
        await show_admin_panel(callback)
    else:
        await callback.answer("Тільки адміністратор може керувати цим статусом\\.", show_alert=True)


# --- ХЕНДЛЕРИ КНОПОК КОРИСТУВАЧА ---

@dp.callback_query(F.data == "get_combo")
async def process_get_combo(callback: types.CallbackQuery):
    """Обробляє натискання кнопки "Отримати комбо зараз"."""
    await callback.answer("Отримуємо комбо...", show_alert=False)
    
    user_id = callback.from_user.id
    is_admin = str(user_id) == ADMIN_ID
    
    combo_text = get_combo_text(is_admin)
    
    # Видаляємо попереднє повідомлення, щоб уникнути дублювання
    try:
        await callback.message.delete()
    except Exception:
        pass 
    
    await callback.message.answer(combo_text, parse_mode=ParseMode.MARKDOWN_V2)


@dp.callback_query(F.data == "manage_activation")
async def process_manage_activation(callback: types.CallbackQuery):
    """Обробляє натискання "Управління активацією" (для Premium або Адмін-панелі)."""
    if str(callback.from_user.id) == ADMIN_ID:
        await callback.answer("Перехід до панелі адміністратора", show_alert=False)
        await show_admin_panel(callback)
    else:
        await callback.answer("Управління активацією Premium", show_alert=False)
        # Реалізація оплати Premium
        await callback.message.answer("Тут буде панель управління активацією Premium \\(з Crypto Bot\\)\\.", parse_mode=ParseMode.MARKDOWN_V2)

@dp.callback_query(F.data == "back_to_start")
async def process_back_to_start(callback: types.CallbackQuery):
    """Повернення з панелі адміністратора до /start."""
    await callback.answer("Повернення до головного меню", show_alert=False)
    # Імітуємо команду /start
    await command_start_handler(callback.message)


# --- ФОНОВЕ ВИКОНАННЯ СКРАПЕРА ---

async def start_scheduler_task():
    """Запускає основну функцію скрапера у фоновому режимі (в окремому потоці)."""
    logger.info("Запуск планувальника скрапінгу у фоновому режимі...")
    # asyncio.to_thread використовується для запуску синхронної функції 
    # скрапера в окремому потоці, щоб не блокувати aiogram
    await asyncio.to_thread(hamster_scraper.main_scheduler) 

async def main() -> None:
    """Головна функція запуску бота та планувальника."""
    logger.info("Бот запущено. Починаю отримувати оновлення...")

    # Запускаємо планувальник скрапінгу як фонову задачу
    asyncio.create_task(start_scheduler_task())
    
    # Запускаємо опитування (polling) бота
    await dp.start_polling(bot)
    
    logger.info("Бот зупинено.")

if __name__ == "__main__":
    try:
        # Використовуємо asyncio.run для запуску головної асинхронної функції
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Критична помилка при запуску: {e}")
