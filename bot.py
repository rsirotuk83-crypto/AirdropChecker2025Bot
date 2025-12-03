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

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# --- Налаштування змінних середовища ---
# Зчитуємо змінні з Railway
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
USER_SUBSCRIPTIONS = {}
IS_ACTIVE = False # Глобальний стан активації комбо

# --- Основні функції бота ---

# Ініціалізація бота
def setup_bot():
    """Створює екземпляр бота з коректними налаштуваннями для aiogram 3.x."""
    bot_properties = DefaultBotProperties(
        parse_mode=ParseMode.MARKDOWN_V2,
        # Залишаємо disable_web_page_preview, оскільки він має підтримуватися
        # у нових версіях DefaultBotProperties
    )
    return Bot(token=BOT_TOKEN, default=bot_properties)

# --- Хелпер для Admin Menu ---

def _build_admin_menu_content():
    """Створює текст та клавіатуру для меню адміністратора."""
    global IS_ACTIVE
    status_text = "*АКТИВНО*" if IS_ACTIVE else "*НЕАКТИВНО*"
    
    if IS_ACTIVE:
        button_text = "🔴 Деактивувати комбо (Тільки для Premium)"
        callback = "deactivate_combo"
    else:
        button_text = "🟢 Активувати комбо (Доступно всім)"
        callback = "activate_combo"
        
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=button_text, callback_data=callback)],
        # Додаємо кнопку "Назад" на випадок, якщо знадобиться
        [types.InlineKeyboardButton(text="⬅️ Назад до /start", callback_data="back_to_start")]
    ])
    
    text = (
        f"⚙️ **Панель адміністратора**\n\n"
        f"Поточний стан відображення комбо для всіх користувачів: {status_text}\n\n"
        "Натисніть кнопку, щоб змінити стан\\."
    )
    return text, keyboard

# Хелпер для /start (тепер використовується і для "Назад")
def _build_start_message_content(user_name: str, user_id: int, is_admin: bool):
    """Створює текст та клавіатуру для початкового повідомлення /start."""
    global IS_ACTIVE
    
    status_text = ""
    keyboard = None
    
    if is_admin:
        status_text = f"**Ваш ID:** `{user_id}`\n**Статус:** Адміністратор\\.\n**Активність:** {'*АКТИВНО*' if IS_ACTIVE else '*НЕАКТИВНО*'}\n\n"
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Управління активацією", callback_data="admin_menu")]
        ])
    else:
        status_text = f"**Ваш ID:** `{user_id}`\n"
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отримати Premium 🔑", callback_data="get_premium")],
        ])

    welcome_message = (
        f"👋 Привіт, {user_name}\\!\n\n"
        f"{status_text}"
        "Цей бот надає ранній доступ до щоденних комбо та кодів для популярних криптоігор\\.\n\n"
        "**Ціна Premium:** 1 TON \\(або еквівалент\\)\\."
    )
    return welcome_message, keyboard


# Хендлер команди /start (БЕЗ ДЕКОРАТОРА)
async def command_start_handler(message: types.Message) -> None:
    """Обробляє команду /start і показує статус підписки."""
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    
    welcome_message, keyboard = _build_start_message_content(message.from_user.first_name, user_id, is_admin)
    
    await message.answer(welcome_message, reply_markup=keyboard)

# Хендлер команди /combo (БЕЗ ДЕКОРАТОРА)
async def command_combo_handler(message: types.Message) -> None:
    """Обробляє команду /combo."""
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    
    if is_admin or IS_ACTIVE:
        # Комбо, яке бачать преміум-користувачі та адмін
        combo_text = f"""
📅 **Комбо та коди на {datetime.now().strftime('%d.%m.%Y')}**
*(Ранній доступ Premium)*
        
*Hamster Kombat* \\rightarrow Pizza \\rightarrow Wallet \\rightarrow Rocket
*Blum* \\rightarrow Cipher: FREEDOM
*TapSwap* \\rightarrow MATRIX
*CATS* \\rightarrow MEOW2025
*Rocky Rabbit* \\rightarrow 3\\rightarrow1\\rightarrow4\\rightarrow2
*Yescoin* \\rightarrow ⬆️\\rightarrow⬇️\\rightarrow⬆️
*DOGS* \\rightarrow DOGS2025
*PixelTap* \\rightarrow FIRE ✨
*W\\-Coin* \\rightarrow A\\rightarrow B\\rightarrow C\\rightarrow D
*Memefi* \\rightarrow LFG
*DotCoin* \\rightarrow PRO
*BountyBot* \\rightarrow BTC
*NEAR Wallet* \\rightarrow BONUS
*Hot Wallet* \\rightarrow MOON
*Avagold* \\rightarrow GOLD
*CEX\\.IO* \\rightarrow STAKE
*Pocketfi* \\rightarrow POCKET
*Seedify* \\rightarrow SEED
*QDROP* \\rightarrow AIRDROP
*MetaSense* \\rightarrow MET
*SQUID* \\rightarrow FISH
        
**\\+ ще 5\\-7 рідкісних комбо...**
        """
        await message.answer(combo_text)
    else:
        # Повідомлення для непідписаних користувачів
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отримати Premium 🔑", callback_data="get_premium")],
        ])
        await message.answer(
            # ВИПРАВЛЕНО: Екрануємо '!' в повідомленні про відсутність підписки
            "🔒 **Увага\\!** Щоб отримати актуальні комбо та коди, вам потрібна Premium\\-підписка\\!\n\n"
            "Натисніть кнопку нижче, щоб оформити ранній доступ\\.",
            reply_markup=keyboard
        )

# Хендлер команди /admin_menu (БЕЗ ДЕКОРАТОРА)
async def admin_menu_handler(message: types.Message):
    """Меню для активації/деактивації комбо (доступно лише адміністратору)."""
    # Цей хендлер використовується для команди, тому надсилає НОВЕ повідомлення
    text, keyboard = _build_admin_menu_content()
    await message.answer(text, reply_markup=keyboard)

# Хендлер для Inline-кнопок (БЕЗ ДЕКОРАТОРА)
async def inline_callback_handler(callback: types.CallbackQuery):
    """Обробляє натискання Inline-кнопок."""
    global IS_ACTIVE
    user_id = callback.from_user.id
    
    # Обробка команд активації/деактивації та навігації (Тільки для адміна)
    if user_id == ADMIN_ID:
        
        # Обробка "Назад"
        if callback.data == "back_to_start":
            welcome_message, keyboard = _build_start_message_content(
                callback.from_user.first_name, 
                user_id, 
                True
            )
            await callback.answer("Повернення до головного меню...")
            await callback.message.edit_text(welcome_message, reply_markup=keyboard)
            return
            
        # Обробка дій в меню адміністратора
        if callback.data == "activate_combo":
            IS_ACTIVE = True
            await callback.answer("Комбо активовано!")
            text, keyboard = _build_admin_menu_content()
            # Редагуємо повідомлення, щоб оновити клавіатуру
            await callback.message.edit_text(text, reply_markup=keyboard) 
            return
            
        elif callback.data == "deactivate_combo":
            IS_ACTIVE = False
            await callback.answer("Комбо деактивовано!")
            text, keyboard = _build_admin_menu_content()
            # Редагуємо повідомлення, щоб оновити клавіатуру
            await callback.message.edit_text(text, reply_markup=keyboard) 
            return
            
        elif callback.data == "status_info":
            await callback.answer(f"Комбо зараз: {'АКТИВНО' if IS_ACTIVE else 'НЕАКТИВНО'}")
            return
            
        elif callback.data == "admin_menu":
            # Обробка натискання кнопки "Управління активацією"
            await callback.answer("Відкриваю адмін-меню...")
            text, keyboard = _build_admin_menu_content()
            # Редагуємо повідомлення (/start), щоб показати меню адміністратора
            await callback.message.edit_text(text, reply_markup=keyboard)
            return

    # Обробка кнопки "Отримати Premium" (для звичайних користувачів)
    if callback.data == "get_premium":
        await callback.answer("Переадресація на оплату...", show_alert=False)
        
        # 1. Створення інвойсу через Crypto Bot API
        try:
            # Для цього прикладу, ми не знаємо BOT_USERNAME, тому передаємо 0
            # У реальному застосуванні, вам потрібно буде отримати username бота (наприклад, через getMe())
            invoice_data = await create_invoice_request(callback.from_user.id, bot_username='0')
            
            if invoice_data and invoice_data.get('ok') and invoice_data['result']['pay_url']:
                pay_url = invoice_data['result']['pay_url']
                invoice_id = invoice_data['result']['invoice_id']
                
                # Кнопки для оплати
                keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="Сплатити (Crypto Bot)", url=pay_url)],
                    [types.InlineKeyboardButton(text="Я сплатив 💸", callback_data=f"check_payment_{invoice_id}")]
                ])
                
                await callback.message.answer(
                    "💰 **Оплата Premium**\n\n"
                    "Для отримання раннього доступу сплатіть 1 TON (або еквівалент)\\.\n"
                    "Натисніть кнопку 'Сплатити' і після оплати — 'Я сплатив 💸'\\.",
                    reply_markup=keyboard
                )
            else:
                await callback.message.answer("⚠️ Не вдалося створити платіжний інвойс\\. Спробуйте пізніше\\.") # Екрануємо '.'
                
        except Exception as e:
            logging.error(f"Помилка створення інвойсу: {e}")
            await callback.message.answer("❌ Сталася помилка при підключенні до платіжної системи\\.") # Екрануємо '.'
            
# Обробка кнопки "Я сплатив" (БЕЗ ДЕКОРАТОРА)
async def check_payment_handler(callback: types.CallbackQuery):
    """Перевірка статусу платежу через API Crypto Bot."""
    invoice_id = callback.data.split('_')[-1]
    
    # 1. Запит статусу інвойсу
    try:
        payment_info = await check_invoice_status(invoice_id)
        
        if payment_info and payment_info.get('ok'):
            status = payment_info['result']['status']
            
            if status == 'paid':
                # Успішна оплата
                await callback.message.edit_text(
                    "🎉 **Оплата успішна\\!** Ви отримали Premium\\-доступ\\.\n" # Екрануємо '!'
                    "Надішліть `/combo` для отримання актуальних кодів\\."
                )
                await callback.answer("Підписка активована!", show_alert=True)
                # Тут мала б бути логіка збереження підписки у базу даних
                return
            
            elif status == 'pending':
                await callback.answer("Платіж ще обробляється\\. Спробуйте через хвилину\\.") # Екрануємо '.'
                return
            
            elif status == 'expired':
                await callback.message.edit_text(
                    "❌ **Термін дії інвойсу сплив\\.** Будь ласка, створіть новий інвойс для оплати\\." # Екрануємо '.'
                )
                await callback.answer("Термін дії сплив\\.", show_alert=True) # Екрануємо '.'
                return
                
            else: # refunded, failed
                await callback.message.answer("Статус платежу: " + status)
        
        else:
            await callback.answer("Не вдалося отримати статус інвойсу\\. Зверніться до адміністратора\\.") # Екрануємо '.'
            
    except Exception as e:
        logging.error(f"Помилка перевірки статусу платежу: {e}")
        await callback.answer("❌ Сталася помилка при перевірці платежу\\.", show_alert=True) # Екрануємо '.'


# --- HTTP запити до Crypto Bot API ---

async def create_invoice_request(user_id: int, bot_username: str):
    """Створює інвойс на 1 TON через Crypto Bot API."""
    url = f"{CRYPTO_BOT_API_URL}/createInvoice"
    
    is_testnet = os.getenv("IS_TESTNET", "false").lower() == "true"
    
    payload = {
        "asset": "TON",
        "amount": "1", # Фіксована ціна 1 TON
        "description": "Ранній доступ до Crypto Combo/Кодів",
        "hidden_message": f"User ID: {user_id}",
        "paid_btn_name": "callback",
        "paid_btn_url": f"t.me/{bot_username}", # Повертає користувача до бота
        "allow_anonymous": False,
        "payload": json.dumps({"user_id": user_id}), # Додаткові дані, які повернуться після оплати
        "is_test": is_testnet
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=API_HEADERS, json=payload, timeout=10.0)
        response.raise_for_status() # Викликає виняток для HTTP помилок
        return response.json()

async def check_invoice_status(invoice_id: str):
    """Перевіряє статус інвойсу за ID."""
    url = f"{CRYPTO_BOT_API_URL}/getInvoices"
    
    payload = {
        "invoice_ids": [invoice_id]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=API_HEADERS, json=payload, timeout=10.0)
        response.raise_for_status()
        
        data = response.json()
        if data.get('ok') and data['result']:
            # API повертає список, беремо перший елемент
            return {'ok': True, 'result': data['result'][0]}
            
        return data

# --- Запуск бота ---

async def main() -> None:
    """Головна функція запуску бота. Тут відбувається коректна реєстрація хендлерів."""
    bot = setup_bot()
    dp = Dispatcher()

    # КОРЕКТНА РЕЄСТРАЦІЯ ХЕНДЛЕРІВ
    
    # 1. Команди (Message Handlers)
    dp.message.register(command_start_handler, CommandStart())
    dp.message.register(command_combo_handler, Command("combo"))
    
    # Реєстрація адмін-меню тільки для ADMIN_ID
    dp.message.register(admin_menu_handler, Command("admin_menu"), F.from_user.id == ADMIN_ID)

    # 2. Обробники Callback (Inline Button Handlers)
    # Реєстрація загальних колбеків
    dp.callback_query.register(
        inline_callback_handler, 
        F.callback_query.data.in_({"get_premium", "admin_menu", "activate_combo", "deactivate_combo", "status_info", "back_to_start"})
    )
    
    # Реєстрація колбека перевірки платежу
    dp.callback_query.register(
        check_payment_handler, 
        F.callback_query.data.startswith("check_payment_")
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
