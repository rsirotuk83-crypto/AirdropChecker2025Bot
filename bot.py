import os
import asyncio
import logging
import json
import httpx
from datetime import datetime
from typing import Dict, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest # ІМПОРТУЄМО ДЛЯ ОБРОБКИ ПОМИЛОК

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

# Стан підписки (імітація бази даних в пам'яті)
# Ключ: user_id (int), Значення: True (bool)
USER_SUBSCRIPTIONS: Dict[int, bool] = {} 
IS_ACTIVE = False # Глобальний стан активації комбо

# --- Утиліти для екранування ---

def escape_all_except_formatting(text: str) -> str:
    """
    Екранує ВСІ спеціальні символи Markdown V2, крім тих, 
    що використовуються для необхідного форматування (** та `). 
    """
    
    # СИМВОЛИ ДЛЯ ЕКРАНУВАННЯ (Згідно з правилами MarkdownV2)
    # _, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !
    
    # 1. Екрануємо зворотний слеш сам по собі ПЕРШИМ
    text = text.replace('\\', r'\\\\')
    
    # 2. Агресивне екранування всіх критичних символів
    # Примітка: * та ` не екрануємо, щоб зберегти жирний шрифт та inline-код.
    
    text = text.replace('_', r'\_')
    text = text.replace('[', r'\[')
    text = text.replace(']', r'\]')
    text = text.replace('(', r'\(')
    text = text.replace(')', r'\)')
    text = text.replace('~', r'\~')
    text = text.replace('>', r'\>')
    text = text.replace('#', r'\#')
    text = text.replace('+', r'\+')
    text = text.replace('-', r'\-')
    text = text.replace('=', r'\=')
    text = text.replace('|', r'\|')
    text = text.replace('{', r'\{')
    text = text.replace('}', r'\}')
    text = text.replace('.', r'\.')
    text = text.replace('!', r'\!')
    
    return text


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
    
    # Формування тексту статусу
    status_text_parts = [
        f"Ваш ID: `{user_id}`",
        f"Статус Premium: {premium_status}"
    ]
    
    if is_admin:
        status_text_parts.append(f"Глобальна Активність: {combo_status}")

    status_text_raw = "\n".join(status_text_parts) + "\n\n"
    status_text = escape_all_except_formatting(status_text_raw)
    
    # ВИПРАВЛЕНО: Використовуємо сирий рядок r"""...""" для уникнення SyntaxWarning
    welcome_message_raw = r"""
👋 Привіт, **{escaped_user_name}**!

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
    global IS_ACTIVE
    
    status_text = r'**АКТИВНО**' if IS_ACTIVE else r'**НЕАКТИВНО**'
    
    if IS_ACTIVE:
        button_text = "🔴 Деактивувати глобальне комбо"
        callback = "deactivate_combo"
    else:
        button_text = "🟢 Активувати глобальне комбо"
        callback = "activate_combo"
        
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=button_text, callback_data=callback)],
        [types.InlineKeyboardButton(text="⬅️ Назад до /start", callback_data="back_to_start")]
    ])
    
    # ВИПРАВЛЕНО: Використовуємо сирий рядок r"""...""" для уникнення SyntaxWarning
    base_text_raw = r"""
⚙️ **Панель адміністратора**

Поточний стан відображення комбо для всіх користувачів (Global Combo): {status_text}

Натисніть кнопку, щоб змінити стан\.
""".format(status_text=status_text)
    
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

# Хендлер команди /combo (ТЕПЕР ПРИЙМАЄ bot)
async def command_combo_handler(message: types.Message, bot: Bot) -> None:
    """Обробляє команду /combo."""
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    is_premium = USER_SUBSCRIPTIONS.get(user_id, False)
    
    # КЛЮЧОВА ЛОГІКА ДОСТУПУ: Адмін АБО Глобальна Активація АБО Індивідуальна Преміум-підписка
    if is_admin or IS_ACTIVE or is_premium:
        # ВИПРАВЛЕНО: Використовуємо сирий рядок r"""...""" для уникнення SyntaxWarning
        combo_text_raw = r"""
📅 **Комбо та коди на {date_str}**
*(Ранній доступ Premium)*
        
*Hamster Kombat* \u2192 Pizza \u2192 Wallet \u2192 Rocket
*Blum* \u2192 Cipher: FREEDOM
*TapSwap* \u2192 MATRIX
*CATS* \u2192 MEOW2025
*Rocky Rabbit* \u2192 3\u21921\u21924\u21922
*Yescoin* \u2192 \u2191\u2192\u2193\u2192\u2191
*DOGS* \u2192 DOGS2025
*PixelTap* \u2192 FIRE ✨
*W-Coin* \u2192 A\u2192B\u2192C\u2192D
*Memefi* \u2192 LFG
*DotCoin* \u2192 PRO
*BountyBot* \u2192 BTC
*NEAR Wallet* \u2192 BONUS
*Hot Wallet* \u2192 MOON
*Avagold* \u2192 GOLD
*CEX\.IO* \u2192 STAKE 
*Pocketfi* \u2192 POCKET
*Seedify* \u2192 SEED
*QDROP* \u2192 AIRDROP
*MetaSense* \u2192 MET
*SQUID* \u2192 FISH
        
**\+ ще 5-7 рідкісних комбо\.\.\.**
        """.format(date_str=datetime.now().strftime(r'%d\.%m\.%Y'))
        
        final_combo_text = escape_all_except_formatting(combo_text_raw)
        
        try:
            # ВИПРАВЛЕНО: Використовуємо bot.send_message
            await bot.send_message(chat_id=message.chat.id, text=final_combo_text)
        except TelegramBadRequest as e:
            logging.error(f"Помилка TelegramBadRequest при відправці комбо: {e}")
            
            # ВИПРАВЛЕНО: Використовуємо bot.send_message
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
        
        # ВИПРАВЛЕНО: Використовуємо сирий рядок r"""...""" для уникнення SyntaxWarning
        premium_message_raw = r"""
🔒 **Увага\!** Щоб отримати актуальні комбо та коди, вам потрібна Premium\-підписка\.

Натисніть кнопку нижче, щоб оформити ранній доступ\.
""" 
        premium_message = escape_all_except_formatting(premium_message_raw)
        
        # ВИПРАВЛЕНО: message.answer() може використовуватись, оскільки це обробник команди Message, 
        # і message вже прив'язаний до bot.
        await message.answer(
            premium_message,
            reply_markup=keyboard
        )

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
            await callback.answer("Комбо активовано!")
            text, keyboard = _build_admin_menu_content()
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2) 
            return
            
        elif callback.data == "deactivate_combo":
            IS_ACTIVE = False
            await callback.answer("Комбо деактивовано!")
            text, keyboard = _build_admin_menu_content()
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2) 
            return
            
        elif callback.data == "admin_menu":
            await callback.answer("Відкриваю адмін-меню...")
            text, keyboard = _build_admin_menu_content()
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
            return
            
    # Обробка кнопки "Отримати Premium" (для звичайних користувачів)
    if callback.data == "get_premium":
        # Перевірка: якщо адмін, то не створюємо інвойс, а активуємо вручну (для тестування)
        if user_id == ADMIN_ID:
             USER_SUBSCRIPTIONS[user_id] = True 
             await callback.answer("Для адміністратора Premium активовано автоматично!")
             # Повертаємося в головне меню, щоб оновити кнопки
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
                
                # ВИПРАВЛЕНО: Використовуємо сирий рядок r"""...""" для уникнення SyntaxWarning
                payment_message_raw = r"""
💰 **Оплата Premium**

Для отримання раннього доступу сплатіть 1 TON (або еквівалент)\.
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
        # Перенаправлення на обробник /combo
        await callback.answer("Отримуємо комбо...")
        # Створюємо імітацію об'єкта Message
        mock_message = types.Message(message_id=callback.message.message_id, 
                                     chat=callback.message.chat, 
                                     from_user=callback.from_user, 
                                     date=datetime.now())
                                     
        # ВИПРАВЛЕНО: ТЕПЕР ПЕРЕДАЄМО bot ЯВНО, щоб message.answer() працювало через bot.send_message
        await command_combo_handler(mock_message, bot)


# Обробка кнопки "Я сплатив"
async def check_payment_handler(callback: types.CallbackQuery):
    """Перевірка статусу платежу через API Crypto Bot."""
    invoice_id = callback.data.split('_')[-1]
    user_id = callback.from_user.id
    
    # 1. Запит статусу інвойсу
    try:
        payment_info = await check_invoice_status(invoice_id)
        
        if payment_info and payment_info.get('ok'):
            status = payment_info['result']['status']
            
            if status == 'paid':
                USER_SUBSCRIPTIONS[user_id] = True 
                
                # ВИПРАВЛЕНО: Використовуємо сирий рядок r"""...""" для уникнення SyntaxWarning
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
                # ВИПРАВЛЕНО: Використовуємо сирий рядок r"""...""" для уникнення SyntaxWarning
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
                await callback.answer("Статус платежу: " + escape_all_except_formatting(status), show_alert=True)
        
        else:
            await callback.answer(r"Не вдалося отримати статус інвойсу\. Зверніться до адміністратора\.")
            
    except Exception as e:
        logging.error(f"Помилка перевірки статусу платежу: {e}")
        await callback.answer(r"❌ Сталася помилка при перевірці платежу\.", show_alert=True)


# --- HTTP запити до Crypto Bot API ---

# (create_invoice_request та check_invoice_status залишаються без змін)
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
    
    # Використовуємо експоненційну затримку для запитів
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=API_HEADERS, json=payload, timeout=10.0)
                response.raise_for_status() # Викликає виняток для HTTP помилок
                return response.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if attempt < 2:
                delay = 2 ** attempt
                await asyncio.sleep(delay)
            else:
                logging.error(f"Помилка API Crypto Bot після 3 спроб: {e}")
                raise e
    # Повертаємо порожній словник у разі невдачі після спроб
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
                    # API повертає список, беремо перший елемент
                    return {'ok': True, 'result': data['result'][0]}
                
                return data
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if attempt < 2:
                delay = 2 ** attempt
                await asyncio.sleep(delay)
            else:
                logging.error(f"Помилка перевірки статусу Crypto Bot після 3 спроб: {e}")
                raise e
    
    # Повертаємо порожній словник у разі невдачі після спроб
    return {}

# --- Запуск бота ---

async def main() -> None:
    """Головна функція запуску бота. Тут відбувається коректна реєстрація хендлерів."""
    bot = setup_bot()
    dp = Dispatcher()

    # КОРЕКТНА РЕЄСТРАЦІЯ ХЕНДЛЕРІВ
    
    # 1. Команди (Message Handlers)
    dp.message.register(command_start_handler, CommandStart())
    # ВИПРАВЛЕНО: Реєструємо команду /combo з обов'язковим передаванням бота
    dp.message.register(command_combo_handler, Command("combo"))
    
    # Реєстрація адмін-меню тільки для ADMIN_ID
    dp.message.register(admin_menu_handler, Command("admin_menu"), F.from_user.id == ADMIN_ID)

    # 2. Обробники Callback (Inline Button Handlers)
    # Реєстрація загальних колбеків
    dp.callback_query.register(
        inline_callback_handler, 
        F.data.in_({"get_premium", "admin_menu", "activate_combo", "deactivate_combo", "status_info", "back_to_start", "show_combo"})
    )
    
    # Реєстрація колбека перевірки платежу
    dp.callback_query.register(
        check_payment_handler, 
        F.data.startswith("check_payment_")
    )

    logging.info("Бот запущено. Починаю отримувати оновлення...")
    # Починаємо обробку оновлень
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main()) 
    except KeyboardInterrupt:
        logging.info("Бот зупинено вручну.")
    except Exception as e:
        logging.critical(f"Критична помилка при запуску: {e}")
