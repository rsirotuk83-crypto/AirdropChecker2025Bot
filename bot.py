import os
import asyncio
import logging
import json
import httpx
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramConflictError # Додано ConflictError

# --- Налаштування логування ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Змінні Оточення ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID") # Змінна для вашого ID

# Спроба перетворити ADMIN_ID на int, якщо вона встановлена
try:
    if ADMIN_ID:
        ADMIN_ID = int(ADMIN_ID)
        logging.info(f"ADMIN_ID встановлено: {ADMIN_ID}")
    else:
        logging.warning("ПОПЕРЕДЖЕННЯ: ADMIN_ID не встановлено. Адмін-функції не будуть доступні.")
except (ValueError, TypeError):
    ADMIN_ID = None
    logging.error("КРИТИЧНА ПОМИЛКА: ADMIN_ID не встановлено або некоректне. Адмін-функції вимкнено.")

# --- Константа для шляху до файлу бази даних ---
DATA_DIR = "/app/data"
DB_FILE = os.path.join(DATA_DIR, "db.json")

# --- Глобальні змінні стану (завантажуються з db.json) ---
# Ці значення будуть оновлюватися функцією load_state
GLOBAL_COMBO_CARDS = None
GLOBAL_COMBO_ACTIVATION_STATUS = True # True - активне (видно всім), False - неактивне (видно лише преміум/адміну)
COMBO_URL = None
PREMIUM_USERS = {} # {user_id: datetime_expiry}

# --- Функції роботи з даними (Persistence) ---

def initialize_data_dir():
    """Перевіряє та створює директорію даних."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        logging.info(f"Перевірено або створено директорію даних: {DATA_DIR}")

def load_state():
    """Завантажує глобальні змінні стану з db.json."""
    global GLOBAL_COMBO_ACTIVATION_STATUS, PREMIUM_USERS, COMBO_URL
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                data = json.load(f)
                GLOBAL_COMBO_ACTIVATION_STATUS = data.get('global_combo_active', True)
                PREMIUM_USERS = data.get('premium_users', {})
                COMBO_URL = data.get('combo_url', None)
                logging.info("Дані успішно завантажено з db.json.")
        except Exception as e:
            logging.error(f"Помилка завантаження даних з db.json: {e}")
            # Використання початкових значень
            GLOBAL_COMBO_ACTIVATION_STATUS = True
            PREMIUM_USERS = {}
            COMBO_URL = None
            logging.warning("Будуть використані початкові значення.")
    else:
        logging.warning(f"Файл бази даних {DB_FILE} не знайдено. Будуть використані початкові значення.")
        GLOBAL_COMBO_ACTIVATION_STATUS = True
        PREMIUM_USERS = {}
        COMBO_URL = None
        
def save_state():
    """Зберігає глобальні змінні стану в db.json."""
    data = {
        'global_combo_active': GLOBAL_COMBO_ACTIVATION_STATUS,
        'premium_users': PREMIUM_USERS,
        'combo_url': COMBO_URL
    }
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(data, f, indent=4)
            logging.info("Дані успішно збережено.")
    except Exception as e:
        logging.error(f"Помилка збереження даних в db.json: {e}")

# --- Функції перевірки статусу ---

def is_admin(user_id):
    """Перевіряє, чи є користувач адміністратором."""
    # ВИКОРИСТАННЯ ВАШОГО ID ЗІ СКРІНШОТІВ ДЛЯ АДМІН-ДОСТУПУ
    HARDCODED_ADMIN_ID = 558992465
    if user_id == HARDCODED_ADMIN_ID:
        return True
    
    if ADMIN_ID is None:
        return False
        
    return user_id == ADMIN_ID

def is_premium(user_id):
    """
    Перевіряє, чи має користувач преміум-доступ.
    Тепер включає ЛОГІКУ ПОЖИТТЄВОГО ПРЕМІУМУ ДЛЯ АДМІНА.
    """
    # 1. Пожиттєвий преміум для адміністратора
    if is_admin(user_id):
        return True
    
    # 2. Звичайна перевірка преміум-підписки (за датою закінчення)
    if str(user_id) in PREMIUM_USERS:
        expiry_date_str = PREMIUM_USERS[str(user_id)]
        try:
            expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d %H:%M:%S.%f")
            return datetime.now() < expiry_date
        except ValueError:
            logging.error(f"Некоректний формат дати для користувача {user_id}")
            return False
    return False

# --- Функція отримання комбо (Scraper) ---

async def fetch_combo_cards(url):
    """Асинхронно завантажує комбо-карти за вказаним URL."""
    global GLOBAL_COMBO_CARDS
    if not url:
        return "*Помилка*: URL для комбо не встановлено."

    try:
        logging.info(f"Спроба завантажити комбо з: {url}")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status() # Викликає виняток для кодів 4xx/5xx

        # Припускаємо, що файл містить чистий текст (комбо)
        combo_text = response.text.strip()
        
        # Перевіряємо, чи отриманий текст виглядає як комбо (не порожній)
        if combo_text:
            GLOBAL_COMBO_CARDS = combo_text
            logging.info("Комбо успішно оновлено.")
            return f"✅ Дані комбо успішно оновлено:\n---\n{combo_text[:100]}..."
        else:
            return "*Помилка*: Отримано порожні дані комбо."

    except httpx.HTTPStatusError as e:
        error_msg = f"*Помилка HTTP*: Не вдалося завантажити комбо. Статус: {e.response.status_code}."
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"*Критична Помилка*: Не вдалося завантажити комбо. Перевірте логі.\nПомилка: {e.__class__.__name__}"
        logging.error(f"Помилка завантаження комбо: {e}", exc_info=True)
        return error_msg

# --- Обробники ---

async def start_command_handler(message: types.Message):
    """Обробник команди /start."""
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "користувач"
    
    is_premium_user = is_premium(user_id)
    
    # Визначаємо статус для відображення в повідомленні
    premium_status_text = "АКТИВНО" if is_premium_user else "НЕАКТИВНО"
    admin_status_text = "*Адміністратор*" if is_admin(user_id) else "*Користувач*"
    global_status_text = "АКТИВНО ✅" if GLOBAL_COMBO_ACTIVATION_STATUS else "ДЕАКТИВОВАНО ❌"
    
    # Клавіатура
    keyboard = [
        [types.InlineKeyboardButton(text=f"Отримати комбо зараз {'🔑' if not is_premium_user else ''}", callback_data="get_combo")],
    ]
    
    # Якщо адміністратор, додаємо кнопку керування
    if is_admin(user_id):
        keyboard.append([types.InlineKeyboardButton(text="Управління активацією ⚙️", callback_data="admin_menu")])

    inline_keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(
        f"👋 Привіт, {user_name}! Ваш ID: `{user_id}`\n\n"
        f"**Статус**: {admin_status_text}\n"
        f"**Статус Premium**: *{premium_status_text}*\n"
        f"**Глобальна Активність**: *{global_status_text}*\n\n"
        "Цей бот надає доступ до щоденних комбо та кодів для популярних криптоігор.",
        reply_markup=inline_keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

# --- Обробник запиту комбо (Callback) ---

async def get_combo_callback_handler(callback_query: types.CallbackQuery):
    """Обробник натискання кнопки 'Отримати комбо'."""
    user_id = callback_query.from_user.id
    
    # Перевірка доступу (адмін/преміум або глобальна активація)
    has_access = is_premium(user_id) or GLOBAL_COMBO_ACTIVATION_STATUS

    if has_access:
        # Доступ дозволено
        if GLOBAL_COMBO_CARDS:
            await callback_query.message.edit_text(
                f"🎉 **Сьогоднішнє комбо:** 🎉\n\n"
                f"{GLOBAL_COMBO_CARDS}\n\n"
                f"**Статус**: Доступ надано ({'Адміністратор' if is_admin(user_id) else 'Premium' if is_premium(user_id) else 'Глобально активне'}).",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="Назад до /start", callback_data="back_to_start")]
                ]),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await callback_query.message.edit_text(
                "⚠️ *Помилка*: Дані комбо ще не завантажено. Спробуйте пізніше.",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="Назад до /start", callback_data="back_to_start")]
                ]),
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        # Доступ заборонено
        await callback_query.answer(
            "Комбо доступне лише для преміум-користувачів або при глобальній активації.",
            show_alert=True
        )
        
        # Показуємо кнопку для активації (замість комбо)
        await callback_query.message.edit_text(
            f"❌ **Доступ обмежено.** ❌\n\n"
            "Щоб отримати щоденне комбо, вам потрібно активувати Преміум-доступ. \n\n"
            "Ваш ID: `{user_id}`",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Підписка Premium 👑 (TODO)", callback_data="activate_combo")],
                [types.InlineKeyboardButton(text="Назад до /start", callback_data="back_to_start")]
            ]),
            parse_mode=ParseMode.MARKDOWN
        )

# --- Обробники для Адмін-панелі ---

async def admin_menu_callback_handler(callback_query: types.CallbackQuery):
    """Показує адмін-меню."""
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Ви не адміністратор!", show_alert=True)
        return

    global GLOBAL_COMBO_ACTIVATION_STATUS
    
    status_text = "АКТИВНО ✅" if GLOBAL_COMBO_ACTIVATION_STATUS else "НЕАКТИВНО ❌"
    
    # Кнопка для перемикання стану
    toggle_text = "Деактивувати глобальне комбо ❌" if GLOBAL_COMBO_ACTIVATION_STATUS else "Активувати глобальне комбо ✅"
    toggle_callback = "deactivate_combo" if GLOBAL_COMBO_ACTIVATION_STATUS else "activate_global_combo"
    
    # Кнопка для оновлення скрапера
    update_text = "Оновити дані комбо (з URL)"
    
    keyboard = [
        [types.InlineKeyboardButton(text=toggle_text, callback_data=toggle_callback)],
        [types.InlineKeyboardButton(text=update_text, callback_data="update_scraper_data")],
        [types.InlineKeyboardButton(text="Встановити URL комбо 🔗", callback_data="set_combo_url")],
        [types.InlineKeyboardButton(text="Назад до /start", callback_data="back_to_start")]
    ]

    await callback_query.message.edit_text(
        f"⚙️ **Панель адміністратора** ⚙️\n\n"
        f"Поточний стан відображення комбо для всіх користувачів (Global Combo): *{status_text}*\n"
        f"Поточний URL комбо: `{COMBO_URL if COMBO_URL else 'Не встановлено'}`",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

# --- Обробники перемикання глобальної активації ---

async def activate_global_combo_callback_handler(callback_query: types.CallbackQuery):
    """Активує глобальне комбо."""
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Ви не адміністратор!")
        return
    
    global GLOBAL_COMBO_ACTIVATION_STATUS
    GLOBAL_COMBO_ACTIVATION_STATUS = True
    save_state()
    
    await callback_query.answer("Глобальне комбо АКТИВОВАНО ✅")
    await admin_menu_callback_handler(callback_query) # Повертаємо в меню

async def deactivate_global_combo_callback_handler(callback_query: types.CallbackQuery):
    """Деактивує глобальне комбо."""
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Ви не адміністратор!")
        return
    
    global GLOBAL_COMBO_ACTIVATION_STATUS
    GLOBAL_COMBO_ACTIVATION_STATUS = False
    save_state()
    
    await callback_query.answer("Глобальне комбо ДЕАКТИВОВАНО ❌")
    await admin_menu_callback_handler(callback_query) # Повертаємо в меню

# --- Обробник оновлення даних комбо ---

async def update_scraper_data_callback_handler(callback_query: types.CallbackQuery):
    """Оновлює глобальну змінну GLOBAL_COMBO_CARDS з COMBO_URL."""
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Ви не адміністратор!")
        return
    
    await callback_query.answer("Починаємо оновлення даних...")
    
    # Повідомляємо користувача, що оновлення триває
    loading_message = await callback_query.message.edit_text(
        "⏳ Оновлення даних комбо... Будь ласка, зачекайте.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Назад до адмін-меню", callback_data="admin_menu")]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Викликаємо функцію завантаження
    result_message = await fetch_combo_cards(COMBO_URL)
    
    # Редагуємо повідомлення з результатом
    await loading_message.edit_text(
        result_message,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Назад до адмін-меню", callback_data="admin_menu")]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

# --- Обробник встановлення URL ---

async def set_combo_url_handler(callback_query: types.CallbackQuery):
    """Просить адміністратора надіслати новий URL."""
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Ви не адміністратор!")
        return
    
    # Встановлюємо стан очікування URL
    await callback_query.message.edit_text(
        "🔗 **Встановлення URL Комбо** 🔗\n\n"
        "Будь ласка, надішліть новий URL-адресу для завантаження щоденного комбо. "
        "Наприклад: `https://raw.githubusercontent.com/cryptocombo/daily/main/combo.txt`",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Скасувати", callback_data="admin_menu")]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )
    # Зберігаємо ID повідомлення, яке потрібно редагувати
    dp.current_message_to_edit = callback_query.message.message_id
    dp.waiting_for_combo_url = True # Встановлюємо флаг очікування

async def handle_new_url_text(message: types.Message):
    """Обробляє отриманий текст як новий URL комбо."""
    if not dp.waiting_for_combo_url or not is_admin(message.from_user.id):
        return

    global COMBO_URL
    new_url = message.text.strip()
    
    if new_url.startswith("http"):
        COMBO_URL = new_url
        save_state()
        
        response_text = f"✅ **URL успішно збережено**:\n`{COMBO_URL}`\n\n"
        
        # Спроба оновити комбо одразу після встановлення URL
        update_result = await fetch_combo_cards(COMBO_URL)
        response_text += update_result

        # Вимикаємо флаг очікування
        dp.waiting_for_combo_url = False
        dp.current_message_to_edit = None
        
        # Видаляємо повідомлення користувача і редагуємо попереднє
        await message.delete()
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=dp.current_message_to_edit or message.message_id, # Редагуємо попереднє повідомлення
                text=response_text,
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="Назад до адмін-меню", callback_data="admin_menu")]
                ]),
                parse_mode=ParseMode.MARKDOWN
            )
        except TelegramBadRequest:
             # На випадок, якщо повідомлення вже відредаговано або видалено
            await message.answer(
                response_text,
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="Назад до адмін-меню", callback_data="admin_menu")]
                ]),
                parse_mode=ParseMode.MARKDOWN
            )
            
    else:
        await message.reply("❌ Некоректний формат URL. URL повинен починатися з `http` або `https`.")

# --- Обробники навігації ---

async def back_to_start_callback_handler(callback_query: types.CallbackQuery):
    """Повертає до /start, редагуючи поточне повідомлення."""
    # Просто викликаємо логіку /start
    await start_command_handler(callback_query.message)
    # Видаляємо "годинник"
    await callback_query.answer()

# --- Головна функція запуску ---

async def main():
    """Основна функція запуску бота."""
    global bot, dp
    
    initialize_data_dir()
    load_state()
    
    if not BOT_TOKEN:
        logging.error("КРИТИЧНА ПОМИЛКА: BOT_TOKEN не встановлено.")
        return

    # Ініціалізація бота та диспетчера
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Стан для очікування URL
    dp.waiting_for_combo_url = False
    dp.current_message_to_edit = None

    # Реєстрація загальних обробників
    dp.message.register(start_command_handler, CommandStart())
    
    # Реєстрація обробника тексту для встановлення URL
    dp.message.register(handle_new_url_text, F.text, F.from_user.id == ADMIN_ID)

    # Реєстрація Callback (Inline Button Handlers)
    dp.callback_query.register(get_combo_callback_handler, F.data == "get_combo")
    dp.callback_query.register(admin_menu_callback_handler, F.data == "admin_menu")
    dp.callback_query.register(activate_global_combo_callback_handler, F.data == "activate_global_combo")
    dp.callback_query.register(deactivate_global_combo_callback_handler, F.data == "deactivate_combo")
    dp.callback_query.register(update_scraper_data_callback_handler, F.data == "update_scraper_data")
    dp.callback_query.register(set_combo_url_handler, F.data == "set_combo_url")
    dp.callback_query.register(back_to_start_callback_handler, F.data == "back_to_start")
    
    logging.info("БОТ УСПІШНО ЗАПУЩЕНО — ПОЧИНАЄМО ПОЛЛІНГ")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("БОТ зупинено вручну.")
    except Exception as e:
        logging.error(f"Критична помилка виконання: {e}", exc_info=True)
