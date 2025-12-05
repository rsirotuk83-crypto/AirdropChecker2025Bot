import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

# Імпорт планувальника скрапінгу
# Вважаємо, що цей файл знаходиться у тій самій директорії, що й bot.py
# --- ЗМІНА: Змінюємо явний імпорт об'єкта на імпорт модуля для уникнення конфліктів.
import hamster_scraper 

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Отримання змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID") # Ваш числовий ID для адмін-команд
# CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN") # Токен для оплати (якщо використовується)

# --- КРИТИЧНЕ ВИПРАВЛЕННЯ ПОМИЛКИ ІНІЦІАЛІЗАЦІЇ (Зберігаємо) ---
def create_bot_instance(token: str) -> Bot:
    """Створює екземпляр бота з властивостями за замовчуванням."""
    if not token:
        logger.critical("BOT_TOKEN не знайдено!")
        raise ValueError("BOT_TOKEN не встановлено.")

    default_properties = DefaultBotProperties(
        parse_mode=ParseMode.MARKDOWN_V2, # Рекомендується для Telegram
        disable_web_page_preview=True,    # Запобігає автоматичному відображенню посилань
        protect_content=False
    )
    return Bot(token=token, default=default_properties)

# Ініціалізація бота та диспетчера
bot = create_bot_instance(BOT_TOKEN)
dp = Dispatcher()

# --- ХЕНДЛЕРИ КОМАНД ---

def get_start_message_text(user_id: int, is_admin: bool) -> str:
    """Формує текст вітального повідомлення, включаючи фікс escape-послідовностей."""
    # Фікс: Використовуємо r-рядок або подвійне екранування, щоб уникнути SyntaxWarning
    # Також використовуємо MarkdownV2 синтаксис (дві підкреслення __)
    
    # Використовуємо простий бекенд-статус
    status_text = "АКТИВОВАНО" if user_id % 2 == 0 else "НЕАКТИВНО" 
    admin_status = "Адміністратор" if is_admin else "Користувач"

    # !!! ФІКС СИНТАКСИЧНОГО ПОПЕРЕДЖЕННЯ:
    # Замінюємо '\.' на '.' або ' \\.' (у цьому випадку ' \.' для MarkdownV2)
    # Щоб уникнути помилок в Python, використовуємо подвійне екранування '\\' для символів MarkdownV2,
    # а для звичайного тексту '.' залишаємо без змін.
    return (
        f"👋 *Привіт, Роман\\!* \n\n"
        f"Ваш ID: `{user_id}`\n"
        f"Статус: *{admin_status}*\n"
        f"Статус Premium: *{status_text}*\n"
        f"Глобальна Активність: НЕАКТИВНО\n\n"
        f"Цей бот надає ранній доступ до щоденних комбо та кодів для популярних криптоігор\\.\n"
        f"Ціна Premium: 1 TON \\(або еквівалент\\)\\." 
    )

@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    """Обробляє команду /start."""
    user_id = message.from_user.id
    is_admin = str(user_id) == ADMIN_ID
    
    text = get_start_message_text(user_id, is_admin)
    
    # Клавіатура
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Отримати комбо зараз ➡️", callback_data="get_combo")],
            [types.InlineKeyboardButton(text="Управління активацією ⚙️", callback_data="manage_activation")],
        ]
    )

    await message.answer(text, reply_markup=keyboard)


# --- ХЕНДЛЕР ДЛЯ КНОПОК ТА ІНШИХ КОМАНД (ПРИКЛАД) ---

@dp.callback_query(F.data == "get_combo")
async def process_get_combo(callback: types.CallbackQuery):
    await callback.answer("Отримуємо комбо...", show_alert=False)
    # Тут має бути логіка отримання актуального комбо з бази даних, яку оновлює скрапер
    await callback.message.answer("Комбо ще не встановлено адміністратором\\.", parse_mode=ParseMode.MARKDOWN_V2)


@dp.callback_query(F.data == "manage_activation")
async def process_manage_activation(callback: types.CallbackQuery):
    await callback.answer("Управління активацією")
    await callback.message.answer("Тут буде панель управління активацією Premium\\.", parse_mode=ParseMode.MARKDOWN_V2)


# --- ФОНОВЕ ВИКОНАННЯ СКРАПЕРА ---

async def start_scheduler_task():
    """Запускає основну функцію скрапера у фоновому режимі."""
    logger.info("Запуск планувальника скрапінгу у фоновому режимі...")
    # --- ЗМІНА: Викликаємо функцію через назву модуля
    await asyncio.to_thread(hamster_scraper.main_scheduler) 

async def main() -> None:
    """Головна функція запуску бота та планувальника."""
    logger.info("Бот запущено. Починаю отримувати оновлення...")

    # Запускаємо планувальник скрапінгу як фонову задачу
    # Ця задача буде працювати паралельно з ботом
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
