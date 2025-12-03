import os
import asyncio
import logging
import json
import httpx
import re
from datetime import datetime
from typing import Dict, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# --- Налаштування змінних середовища ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN or not CRYPTO_BOT_TOKEN or not ADMIN_ID:
    logging.error("ПОМИЛКА: Не встановлено BOT_TOKEN, CRYPTO_BOT_TOKEN або ADMIN_ID в змінних середовища.")
    exit(1)

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    logging.error("ПОМИЛКА: Змінна ADMIN_ID повинна бути числовим ідентифікатором.")
    exit(1)

# API URL Crypto Bot
CRYPTO_BOT_API_URL = "https://pay.crypt.bot/api"
API_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Telegram-Bot-Api-Token": CRYPTO_BOT_TOKEN
}

# --- ГЛОБАЛЬНИЙ СТАН (Імітація БД) ---
DB_FILE = "db_state.json"
USER_SUBSCRIPTIONS: Dict[int, bool] = {} 
IS_ACTIVE = False # Глобальний стан активації комбо
COMBO_CONTENT: str = r"❌ **Комбо ще не встановлено адміністратором\.**" 
# НОВИЙ СТАН ДЛЯ АВТОМАТИЗАЦІЇ
# ЗАЛИШЕНО ПОРОЖНІМ. АДМІНІСТРАТОР ПОВИНЕН ВСТАНОВИТИ ВЛАСНИЙ URL.
AUTO_SOURCE_URL: str = "" 

# --- Утиліти для персистентності (Імітація БД) ---

def load_persistent_state():
    """Завантажує глобальний стан з файлу при старті бота."""
    global USER_SUBSCRIPTIONS, IS_ACTIVE, COMBO_CONTENT, AUTO_SOURCE_URL
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                USER_SUBSCRIPTIONS = {int(k): v for k, v in data.get("subscriptions", {}).items()}
                IS_ACTIVE = data.get("is_active", False)
                COMBO_CONTENT = data.get("combo_content", r"❌ **Комбо ще не встановлено адміністратором\.**")
                # НОВЕ: Завантаження URL
                AUTO_SOURCE_URL = data.get("auto_source_url", "")
            logging.info("Глобальний стан завантажено з файлу.")
        except Exception as e:
            logging.error(f"Помилка завантаження стану з JSON: {e}")
            
def save_persistent_state():
    """Зберігає глобальний стан у файл."""
    global USER_SUBSCRIPTIONS, IS_ACTIVE, COMBO_CONTENT, AUTO_SOURCE_URL
    data = {
        "subscriptions": USER_SUBSCRIPTIONS,
        "is_active": IS_ACTIVE,
        "combo_content": COMBO_CONTENT,
        # НОВЕ: Збереження URL
        "auto_source_url": AUTO_SOURCE_URL
    }
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info("Глобальний стан збережено до файлу.")
    except Exception as e:
        logging.error(f"Помилка збереження стану до JSON: {e}")


# --- Утиліти для екранування ---

MARKDOWN_V2_SPECIAL_CHARS = r"([\[\]()~>#+=|{}.!-])"

def escape_all_except_formatting(text: str) -> str:
    """
    Екранує ВСІ спеціальні символи Markdown V2, крім тих, що використовуються 
    для необхідного форматування (** та `), а також зворотного слеша (\). 
    """
    # Екрануємо зворотний слеш
    text = text.replace('\\', r'\\')
    
    # Екрануємо решту критичних символів
    text = re.sub(MARKDOWN_V2_SPECIAL_CHARS, r'\\\1', text)
    
    # Екрануємо _ та * та `
    text = text.replace('*', r'\*')
    text = text.replace('_', r'\_')
    text = text.replace('`', r'\`') 
    
    # Спроба зберегти **...** та `...`
    # 1. Замінюємо тимчасовим placeholder'ом жирний шрифт (**текст**)
    def replace_bold(match):
        # Прибираємо екранування символів, щоб вони працювали всередині **
        content = match.group(2).replace(r'\*', '*').replace(r'\_', '_').replace(r'\`', '`')
        return f"__TEMP_BOLD_START__{content}__TEMP_BOLD_END__"

    text = re.sub(r'(\*\*([^*]+)\*\*)', replace_bold, text)

    # 2. Замінюємо тимчасовим placeholder'ом inline-код (`текст`)
    def replace_code(match):
        # Прибираємо ВСЕ екранування всередині коду (це коректно для MarkdownV2)
        content = match.group(2).replace('\\', '')
        return f"__TEMP_CODE_START__{content}__TEMP_CODE_END__"

    text = re.sub(r'(`([^`]+)`)', replace_code, text)
    
    # 3. Повертаємо жирний шрифт та inline-код на місце (БЕЗ екранування їх самих)
    text = text.replace("__TEMP_BOLD_START__", r'**').replace("__TEMP_BOLD_END__", r'**')
    text = text.replace("__TEMP_CODE_START__", r'`').replace("__TEMP_CODE_END__", r'`')
    
    # Нарешті, повертаємо * та _ на місце, якщо вони не були частиною форматування.
    text = text.replace(r'\*', '*').replace(r'\_', '_').replace(r'\`', '`')
    
    return text


# --- Фонова задача для автоматизації ---

async def fetch_and_update_combo(bot: Bot):
    """
    Завантажує контент з AUTO_SOURCE_URL і оновлює COMBO_CONTENT.
    """
    global COMBO_CONTENT, AUTO_SOURCE_URL
    
    if not AUTO_SOURCE_URL:
        logging.info("Автоматичне оновлення пропущено: AUTO_SOURCE_URL не встановлено.")
        # Надіслати сповіщення адміністратору про необхідність встановлення URL, якщо він ще не отримував його.
        # Це спростить життя, якщо бот перезавантажився, а URL не був встановлений.
        if COMBO_CONTENT == r"❌ **Комбо ще не встановлено адміністратором\.**":
            notification_raw = r"""
⚠️ **АВТОМАТИЗАЦІЯ НЕ НАЛАШТОВАНА**
Будь ласка, встановіть URL-адресу джерела для автоматичного оновлення, використовуючи команду `\/set\_source\_url`
"""
            try:
                await bot.send_message(
                    chat_id=ADMIN_ID,
                    text=escape_all_except_formatting(notification_raw),
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            except Exception:
                pass # Ігноруємо помилки, якщо адмін заблокував бота
        return
        
    logging.info(f"Починаю автоматичне оновлення з URL: {AUTO_SOURCE_URL}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Припускаємо, що джерело повертає чистий текст (Markdown V2)
            response = await client.get(AUTO_SOURCE_URL)
            response.raise_for_status() # Викликає помилку для 4xx/5xx статусів
            
            new_content = response.text.strip()
            
            if new_content and new_content != COMBO_CONTENT:
                COMBO_CONTENT = new_content
                save_persistent_state() # Зберігаємо новий контент
                logging.info("✅ Успішно оновлено COMBO_CONTENT з зовнішнього джерела.")
                
                # Сповіщення адміністратору про оновлення
                date_str_raw = datetime.now().strftime('%d.%m.%Y')
                date_str_escaped = date_str_raw.replace('.', r'\.')
                
                notification_raw = r"""
⚙️ **АВТОМАТИЧНЕ ОНОВЛЕННЯ УСПІШНЕ**
Контент комбо на {date_str_escaped} оновлено з {source_url}

Перевірте відображення, надіславши `\/combo`
""".format(date_str_escaped=date_str_escaped, source_url=escape_all_except_formatting(AUTO_SOURCE_URL))
                
                await bot.send_message(
                    chat_id=ADMIN_ID,
                    text=escape_all_except_formatting(notification_raw),
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                
            elif new_content == COMBO_CONTENT:
                logging.info("Контент не змінився. Оновлення не потрібне.")
            else:
                logging.warning("Зовнішнє джерело повернуло порожній контент.")
                
    except httpx.RequestError as e:
        logging.error(f"Помилка HTTP при завантаженні комбо: {e}")
        error_message_raw = r"❌ **ПОМИЛКА АВТОМАТИЗАЦІЇ\!** Не вдалося завантажити контент з джерела\. Перевірте URL\."
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=escape_all_except_formatting(error_message_raw),
            parse_mode=ParseMode.MARKDOWN_V2
        )


async def combo_fetch_scheduler(bot: Bot):
    """
    Планувальник для запуску fetch_and_update_combo кожні 24 години.
    """
    # Період оновлення: 24 години (86400 секунд)
    UPDATE_INTERVAL_SECONDS = 86400 
    
    # Чекаємо 10 секунд після старту, щоб дати боту час ініціалізуватися
    await asyncio.sleep(10) 
    
    while True:
        try:
            await fetch_and_update_combo(bot)
        except Exception as e:
            logging.error(f"Критична помилка в планувальнику: {e}")
            
        # Чекаємо наступного циклу
        await asyncio.sleep(UPDATE_INTERVAL_SECONDS)


# --- Основні функції бота ---

# Ініціалізація бота
def setup_bot():
    """Створює екземпляр бота з коректними налаштуваннями для aiogram 3.x."""
    bot_properties = DefaultBotProperties(
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return Bot(token=BOT_TOKEN, default=bot_properties)

# Хелпер для /start (тепер використовується і для "Назад")
def _build_start_message_content(user_name: str, user_id: int, is_admin: bool):
    """Створює текст та клавіатуру для початкового повідомлення /start."""
    
    is_premium = USER_SUBSCRIPTIONS.get(user_id, False) or is_admin

    escaped_user_name = escape_all_except_formatting(user_name)
    
    combo_status = r'**АКТИВНО**' if IS_ACTIVE else r'**НЕАКТИВНО**'
    premium_status = r'**АКТИВОВАНО**' if is_premium else r'**НЕАКТИВОВАНО**'
    
    keyboard = None
    
    # Формування тексту статусу (використовуємо r'' для уникнення проблем з Python escapes)
    status_text_parts = [
        f"Ваш ID: `{user_id}`",
        f"Статус Premium: {premium_status}"
    ]
    
    if is_admin:
        status_text_parts.append(f"Глобальна Активність: {combo_status}")
        # Додаємо статус автооновлення
        source_status_display = "ВСТАНОВЛЕНО" if AUTO_SOURCE_URL else "НЕ ВСТАНОВЛЕНО"
        # Екрануємо статус, оскільки він буде відображатися жирним шрифтом
        source_status = r'**' + escape_all_except_formatting(source_status_display) + r'**'
        status_text_parts.append(f"Автооновлення: {source_status}")


    status_text = "\n".join(status_text_parts) + "\n\n"
    
    # ВИПРАВЛЕНО: Використовуємо сирий рядок r"""...""" для уникнення SyntaxWarning
    welcome_message_raw = r"""
👋 Привіт, **{escaped_user_name}**\!

{status_text}
Цей бот надає ранній доступ до щоденних комбо та кодів для популярних криптоігор\.

**Ціна Premium:** 1 TON (або еквівалент)\.
""".format(escaped_user_name=escaped_user_name, status_text=status_text)
    
    # Створюємо клавіатуру
    if is_admin:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отримати комбо зараз ➡️", callback_data="show_combo")],
            [types.InlineKeyboardButton(text="Управління активацією ⚙️", callback_data="admin_menu")]
        ])
    elif not is_premium:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отримати Premium 🔑", callback_data="get_premium")],
        ])
    else:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отримати комбо зараз ➡️", callback_data="show_combo")],
        ])
        
    final_message = escape_all_except_formatting(welcome_message_raw)
    
    return final_message, keyboard

# Хелпер для Admin Menu
def _build_admin_menu_content():
    """Створює текст та клавіатуру для меню адміністратора."""
    global IS_ACTIVE, AUTO_SOURCE_URL
    
    status_text = r'**АКТИВНО**' if IS_ACTIVE else r'**НЕАКТИВНО**'
    
    if IS_ACTIVE:
        button_text = "🔴 Деактивувати глобальне комбо"
        callback = "deactivate_combo"
    else:
        button_text = "🟢 Активувати глобальне комбо"
        callback = "activate_combo"
        
    # Додаємо кнопку для ручного запуску автооновлення
    auto_update_button = types.InlineKeyboardButton(text="🔄 Запустити автооновлення зараз", callback_data="run_auto_update")
        
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=button_text, callback_data=callback)],
        [auto_update_button],
        [types.InlineKeyboardButton(text="⬅️ Назад до /start", callback_data="back_to_start")]
    ])
    
    source_info = escape_all_except_formatting(AUTO_SOURCE_URL or "Не встановлено")
    
    # ВИПРАВЛЕНО: Використовуємо сирий рядок r"""...""" для уникнення SyntaxWarning
    base_text_raw = r"""
⚙️ **Панель адміністратора**

Поточний стан відображення комбо для всіх користувачів \(Global Combo\): {status_text}

**Джерело автооновлення:** `{source_info}` 
Використовуйте команду `\/set\_source\_url` для зміни джерела\.

Натисніть кнопку, щоб змінити стан або вручну оновити комбо\.
""".format(status_text=status_text, source_info=source_info)
    
    text = escape_all_except_formatting(base_text_raw)
    
    return text, keyboard

# Хендлер команди /start
async def command_start_handler(message: types.Message) -> None:
    """Обробляє команду /start і показує статус підписки."""
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    
    welcome_message, keyboard = _build_start_message_content(
        message.from_user.first_name or "Користувач", 
        user_id, 
        is_admin
    )
    
    await message.answer(welcome_message, reply_markup=keyboard)

# Хендлер команди /combo
async def command_combo_handler(message: types.Message, bot: Bot) -> None:
    """Обробляє команду /combo."""
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    is_premium = USER_SUBSCRIPTIONS.get(user_id, False)
    
    # КЛЮЧОВА ЛОГІКА ДОСТУПУ
    if is_admin or IS_ACTIVE or is_premium:
        
        # 1. Форматуємо дату
        date_str_raw = datetime.now().strftime('%d.%m.%Y')
        date_str_escaped = date_str_raw.replace('.', r'\.')
        
        # 2. Отримуємо вміст
        combo_content_to_send = COMBO_CONTENT
        
        # 3. Створюємо фінальний текст, замінюючи placeholder дати, якщо він є
        if "{date_str}" in COMBO_CONTENT:
            combo_text_with_date = combo_content_to_send.format(date_str=date_str_escaped)
        else:
            # Додаємо дату на початок і екрануємо заголовок
            header = escape_all_except_formatting(f"📅 **Комбо та коди на {date_str_raw}**\n\n")
            combo_text_with_date = header + combo_content_to_send
            
        # 4. Екрануємо вміст, крім жирного та inline-коду
        final_combo_text = escape_all_except_formatting(combo_text_with_date)
        
        try:
            await bot.send_message(chat_id=message.chat.id, text=final_combo_text)
        except TelegramBadRequest as e:
            logging.error(f"Помилка TelegramBadRequest при відправці комбо: {e}")
            
            error_message_raw = r"❌ **Помилка відображення комбо**\. Виникла проблема з форматуванням Telegram\. Спробуйте пізніше або зверніться до адміністратора\."
            await bot.send_message(
                chat_id=message.chat.id, 
                text=escape_all_except_formatting(error_message_raw)
            )
    else:
        # Повідомлення для непідписаних користувачів
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отримати Premium 🔑", callback_data="get_premium")],
        ])
        
        premium_message_raw = r"""
🔒 **Увага\!** Щоб отримати актуальні комбо та коди, вам потрібна Premium\-підписка\.

Натисніть кнопку нижче, щоб оформити ранній доступ\.
""" 
        premium_message = escape_all_except_formatting(premium_message_raw)
        
        await message.answer(
            premium_message,
            reply_markup=keyboard
        )

# НОВИЙ ХЕНДЛЕР: Встановлення нового контенту комбо (Тільки для адміна)
async def command_set_combo(message: types.Message):
    """Дозволяє адміністратору встановити новий текст комбо вручну."""
    global COMBO_CONTENT
    
    new_combo_text = message.text.replace('/set_combo', '', 1).strip()
    
    if not new_combo_text:
        usage_message_raw = r"⚠️ **Використання:** `\/set\_combo \{ваш\_текст\_комбо\_тут\}`"
        await message.answer(escape_all_except_formatting(usage_message_raw))
        return
        
    COMBO_CONTENT = new_combo_text
    save_persistent_state() 

    success_message_raw = r"✅ **Новий контент комбо успішно встановлено вручну\.**"
    await message.answer(escape_all_except_formatting(success_message_raw))
    
    mock_message = types.Message(message_id=message.message_id, 
                                     chat=message.chat, 
                                     from_user=message.from_user, 
                                     date=datetime.now())
    await command_combo_handler(mock_message, message.bot) 

# НОВИЙ ХЕНДЛЕР: Встановлення URL-адреси джерела для автооновлення (Тільки для адміна)
async def command_set_source_url(message: types.Message):
    """Дозволяє адміністратору встановити URL для автоматичного оновлення."""
    global AUTO_SOURCE_URL
    
    new_url = message.text.replace('/set_source_url', '', 1).strip()
    
    if not new_url:
        source_info = escape_all_except_formatting(AUTO_SOURCE_URL or "Не встановлено")
        usage_message_raw = r"""
⚠️ **Використання:** `\/set\_source\_url \{ваш\_url\_тут\}`
Поточний URL: `{source_info}`
"""
        await message.answer(escape_all_except_formatting(usage_message_raw).format(source_info=source_info))
        return
        
    AUTO_SOURCE_URL = new_url
    save_persistent_state() 

    success_message_raw = r"✅ **URL для автооновлення встановлено успішно\!** Спробую завантажити контент зараз\."
    await message.answer(escape_all_except_formatting(success_message_raw))
    
    # Спробуємо одразу запустити оновлення, щоб перевірити
    await fetch_and_update_combo(message.bot)

# Хендлер команди /admin_menu
async def admin_menu_handler(message: types.Message):
    """Меню для активації/деактивації комбо (доступно лише адміністратору)."""
    text, keyboard = _build_admin_menu_content()
    await message.answer(text, reply_markup=keyboard)

# Хендлер для Inline-кнопок
async def inline_callback_handler(callback: types.CallbackQuery, bot: Bot):
    """Обробляє натискання Inline-кнопок."""
    global IS_ACTIVE
    user_id = callback.from_user.id
    
    # Обробка команд активації/деактивації та навігації (Тільки для адміна)
    if user_id == ADMIN_ID:
        
        if callback.data == "back_to_start":
            welcome_message, keyboard = _build_start_message_content(
                callback.from_user.first_name or "Користувач", 
                user_id, 
                True
            )
            await callback.answer("Повернення до головного меню...")
            await callback.message.edit_text(welcome_message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
            return
            
        elif callback.data == "activate_combo":
            IS_ACTIVE = True
            save_persistent_state() 
            await callback.answer("Комбо активовано!")
            text, keyboard = _build_admin_menu_content()
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2) 
            return
            
        elif callback.data == "deactivate_combo":
            IS_ACTIVE = False
            save_persistent_state() 
            await callback.answer("Комбо деактивовано!")
            text, keyboard = _build_admin_menu_content()
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2) 
            return
        
        elif callback.data == "run_auto_update":
            # Ручний запуск автооновлення
            if AUTO_SOURCE_URL:
                await callback.answer("Запускаю ручне оновлення...")
                await fetch_and_update_combo(bot)
                # Оновлюємо адмін-меню після спроби оновлення
                text, keyboard = _build_admin_menu_content()
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2) 
            else:
                await callback.answer("URL джерела не встановлено. Використайте /set_source_url", show_alert=True)
            return

        elif callback.data == "admin_menu":
            await callback.answer("Відкриваю адмін-меню...")
            text, keyboard = _build_admin_menu_content()
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
            return
            
    # Обробка кнопки "Отримати Premium" (для звичайних користувачів)
    if callback.data == "get_premium":
        if user_id == ADMIN_ID:
             USER_SUBSCRIPTIONS[user_id] = True
             save_persistent_state() 
             await callback.answer("Для адміністратора Premium активовано автоматично!")
             welcome_message, keyboard = _build_start_message_content(
                callback.from_user.first_name or "Користувач", 
                user_id, 
                True
            )
             await callback.message.edit_text(welcome_message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
             return
        
        await callback.answer("Переадресація на оплату...", show_alert=False)
        
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.username
            
            invoice_data = await create_invoice_request(callback.from_user.id, bot_username=bot_username)
            
            if invoice_data and invoice_data.get('ok') and invoice_data['result']['pay_url']:
                pay_url = invoice_data['result']['pay_url']
                invoice_id = invoice_data['result']['invoice_id']
                
                keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="Сплатити (Crypto Bot) 💳", url=pay_url)],
                    [types.InlineKeyboardButton(text="Я сплатив 💸 (Перевірити)", callback_data=f"check_payment_{invoice_id}")]
                ])
                
                payment_message_raw = r"""
💰 **Оплата Premium**

Для отримання раннього доступу сплатіть 1 TON \(або еквівалент\)\.
Натисніть кнопку 'Сплатити' і після оплати — 'Я сплатив 💸'\.
"""
                payment_message = escape_all_except_formatting(payment_message_raw)
                
                await callback.message.edit_text(
                    payment_message, 
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                await callback.message.answer(r"⚠️ Не вдалося створити платіжний інвойс\. Спробуйте пізніше\.")
                
        except Exception as e:
            logging.error(f"Помилка створення інвойсу: {e}")
            await callback.message.answer(r"❌ Сталася помилка при підключенні до платіжної системи\.")
            
    elif callback.data == "show_combo":
        await callback.answer("Отримуємо комбо...")
        mock_message = types.Message(message_id=callback.message.message_id, 
                                     chat=callback.message.chat, 
                                     from_user=callback.from_user, 
                                     date=datetime.now())
                                     
        await command_combo_handler(mock_message, bot)


# Обробка кнопки "Я сплатив"
async def check_payment_handler(callback: types.CallbackQuery):
    """Перевірка статусу платежу через API Crypto Bot."""
    invoice_id = callback.data.split('_')[-1]
    user_id = callback.from_user.id
    
    try:
        payment_info = await check_invoice_status(invoice_id)
        
        if payment_info and payment_info.get('ok'):
            status = payment_info['result']['status']
            
            if status == 'paid':
                USER_SUBSCRIPTIONS[user_id] = True 
                save_persistent_state() 
                
                success_message_raw = r"""
🎉 **Оплата успішна\!** Ви отримали Premium\-доступ\.
Надішліть `\/combo` або натисніть кнопку 'Отримати комбо зараз' для актуальних кодів\.
"""
                success_message = escape_all_except_formatting(success_message_raw)
                
                await callback.message.edit_text(
                    success_message, 
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                         [types.InlineKeyboardButton(text="Отримати комбо зараз ➡️", callback_data="show_combo")]
                    ]),
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                await callback.answer("Підписка активована!", show_alert=True)
                return
            
            elif status == 'pending':
                await callback.answer(r"Платіж ще обробляється\. Спробуйте через хвилину\.")
                return
            
            elif status == 'expired':
                expired_message_raw = r"❌ **Термін дії інвойсу сплив\.** Будь ласка, створіть новий інвойс для оплати\."
                expired_message = escape_all_except_formatting(expired_message_raw)
                
                await callback.message.edit_text(
                    expired_message,
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="Створити новий інвойс 🔑", callback_data="get_premium")]
                    ]),
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                await callback.answer(r"Термін дії сплив\.", show_alert=True)
                return
                
            else: # refunded, failed
                safe_status = escape_all_except_formatting(status)
                await callback.answer("Статус платежу: " + safe_status, show_alert=True)
        
        else:
            await callback.answer(r"Не вдалося отримати статус інвойсу\. Зверніться до адміністратора\.")
            
    except Exception as e:
        logging.error(f"Помилка перевірки статусу платежу: {e}")
        await callback.answer(r"❌ Сталася помилка при перевірці платежу\.", show_alert=True)


# --- HTTP запити до Crypto Bot API ---

async def create_invoice_request(user_id: int, bot_username: str) -> dict[str, Any]:
    """Створює інвойс на 1 TON через Crypto Bot API."""
    url = f"{CRYPTO_BOT_API_URL}/createInvoice"
    
    is_testnet = os.getenv("IS_TESTNET", "false").lower() == "true"
    
    payload = {
        "asset": "TON",
        "amount": "1", # Фіксована ціна 1 TON
        "description": "Ранній доступ до Crypto Combo/Кодів",
        "hidden_message": f"User ID: {user_id}",
        "paid_btn_name": "callback",
        "paid_btn_url": f"https://t.me/{bot_username}", # Повертає користувача до бота
        "allow_anonymous": False,
        "payload": json.dumps({"user_id": user_id}), # Додаткові дані, які повернуться після оплати
        "is_test": is_testnet
    }
    
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=API_HEADERS, json=payload, timeout=10.0)
                response.raise_for_status() 
                return response.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if attempt < 2:
                delay = 2 ** attempt
                await asyncio.sleep(delay)
            else:
                logging.error(f"Помилка API Crypto Bot після 3 спроб: {e}")
                return {} 
    return {} 

async def check_invoice_status(invoice_id: str) -> dict[str, Any]:
    """Перевіряє статус інвойсу за ID."""
    url = f"{CRYPTO_BOT_API_URL}/getInvoices"
    
    payload = {
        "invoice_ids": [invoice_id]
    }
    
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=API_HEADERS, json=payload, timeout=10.0)
                response.raise_for_status()
                
                data = response.json()
                if data.get('ok') and data['result']:
                    return {'ok': True, 'result': data['result'][0]}
                
                return data
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if attempt < 2:
                delay = 2 ** attempt
                await asyncio.sleep(delay)
            else:
                logging.error(f"Помилка перевірки статусу Crypto Bot після 3 спроб: {e}")
                return {} 
    
    return {}

# --- Запуск бота ---

async def main() -> None:
    """Головна функція запуску бота. Тут відбувається коректна реєстрація хендлерів."""
    
    load_persistent_state() 
    
    bot = setup_bot()
    dp = Dispatcher()

    # КОРЕКТНА РЕЄСТРАЦІЯ ХЕНДЛЕРІВ
    
    # 1. Команди (Message Handlers)
    dp.message.register(command_start_handler, CommandStart())
    dp.message.register(command_combo_handler, Command("combo"))
    
    # Реєстрація адмін-меню та нової команди /set_combo та /set_source_url тільки для ADMIN_ID
    dp.message.register(admin_menu_handler, Command("admin_menu"), F.from_user.id == ADMIN_ID)
    dp.message.register(command_set_combo, Command("set_combo"), F.from_user.id == ADMIN_ID)
    dp.message.register(command_set_source_url, Command("set_source_url"), F.from_user.id == ADMIN_ID)

    # 2. Обробники Callback (Inline Button Handlers)
    dp.callback_query.register(
        inline_callback_handler, 
        F.data.in_({"get_premium", "admin_menu", "activate_combo", "deactivate_combo", "status_info", "back_to_start", "show_combo", "run_auto_update"})
    )
    
    dp.callback_query.register(
        check_payment_handler, 
        F.data.startswith("check_payment_")
    )
    
    # !!! КРОК 3: Запуск фонової задачі-планувальника
    asyncio.create_task(combo_fetch_scheduler(bot))

    logging.info("Бот запущено. Починаю отримувати оновлення...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main()) 
    except KeyboardInterrupt:
        logging.info("Бот зупинено вручну.")
    except Exception as e:
        logging.critical(f"Критична помилка при запуску: {e}")
