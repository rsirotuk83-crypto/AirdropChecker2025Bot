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
# Зчитуємо змінні з Railway (змінні, які ви вже успішно налаштували)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN or not CRYPTO_BOT_TOKEN or not ADMIN_ID:
    # Цей лог допоможе виявити, якщо змінна не була знайдена
    logging.error("ПОМИЛКА: Не встановлено BOT_TOKEN, CRYPTO_BOT_TOKEN або ADMIN_ID в змінних середовища.")
    # Припиняємо роботу, щоб не використовувати невірні токени
    exit(1)

try:
    # ADMIN_ID повинен бути числовим, тому перетворюємо його
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
IS_ACTIVE = False # Глобальний стан активації комбо (чи можуть його бачити всі)

# --- Основні функції бота ---

# Ініціалізація бота з використанням DefaultBotProperties (ВИПРАВЛЕННЯ ДЛЯ AIOGRAM 3.x)
def setup_bot():
    """Створює екземпляр бота з коректними налаштуваннями для aiogram 3.x."""
    bot_properties = DefaultBotProperties(
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True 
    )
    return Bot(token=BOT_TOKEN, default=bot_properties)

# Хендлер команди /start
@CommandStart()
async def command_start_handler(message: types.Message) -> None:
    """Обробляє команду /start і показує статус підписки."""
    user_id = message.from_user.id
    
    # Перевірка, чи користувач є адміністратором
    is_admin = user_id == ADMIN_ID
    
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
        f"👋 Привіт, {message.from_user.first_name}!\n\n"
        f"{status_text}"
        "Цей бот надає ранній доступ до щоденних комбо та кодів для популярних криптоігор\\.\n\n"
        "**Ціна Premium:** 1 TON \\(або еквівалент\\)\\."
    )
    
    await message.answer(welcome_message, reply_markup=keyboard)

# Хендлер команди /combo (для отримання комбо)
@Command("combo")
async def command_combo_handler(message: types.Message) -> None:
    """Обробляє команду /combo."""
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    
    if is_admin or IS_ACTIVE:
        # Комбо, яке бачать преміум-користувачі та адмін
        combo_text = f"""
📅 **Комбо та коди на {datetime.now().strftime('%d.%m.%Y')}**
*(Ранній доступ Premium)*
        
*Hamster Kombat* \\→ Pizza \\→ Wallet \\→ Rocket
*Blum* \\→ Cipher: FREEDOM
*TapSwap* \\→ MATRIX
*CATS* \\→ MEOW2025
*Rocky Rabbit* \\→ 3\\→1\\→4\\→2
*Yescoin* \\→ ⬆️\\→⬇️\\→⬆️
*DOGS* \\→ DOGS2025
*PixelTap* \\→ FIRE ✨
*W\\-Coin* \\→ A\\→B\\→C\\→D
*Memefi* \\→ LFG
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
            "🔒 **Увага!** Щоб отримати актуальні комбо та коди, вам потрібна Premium\\-підписка\\.\n\n"
            "Натисніть кнопку нижче, щоб оформити ранній доступ\\.",
            reply_markup=keyboard
        )

# Хендлер для меню адміністратора
@Command("admin_menu")
@F.from_user.id == ADMIN_ID
async def admin_menu_handler(message: types.Message):
    """Меню для активації/деактивації комбо (доступно лише адміністратору)."""
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
        [types.InlineKeyboardButton(text=f"Поточний статус: {status_text}", callback_data="status_info")]
    ])
    
    await message.answer(
        f"⚙️ **Панель адміністратора**\n\n"
        f"Поточний стан відображення комбо для всіх користувачів: {status_text}\n\n"
        "Натисніть кнопку, щоб змінити стан\\.",
        reply_markup=keyboard
    )

# Хендлер для Inline-кнопок
@F.callback_query.data.in_({"get_premium", "admin_menu", "activate_combo", "deactivate_combo", "status_info"})
async def inline_callback_handler(callback: types.CallbackQuery):
    """Обробляє натискання Inline-кнопок."""
    global IS_ACTIVE
    user_id = callback.from_user.id
    
    # Обробка команд активації/деактивації (Тільки для адміна)
    if user_id == ADMIN_ID:
        if callback.data == "activate_combo":
            IS_ACTIVE = True
            await callback.message.edit_text("✅ **Успіх!** Комбо тепер доступне для всіх користувачів.", reply_markup=None)
            await callback.answer("Комбо активовано!")
            await asyncio.sleep(1)
            await admin_menu_handler(callback.message)
            return
            
        elif callback.data == "deactivate_combo":
            IS_ACTIVE = False
            await callback.message.edit_text("❌ **Успіх!** Комбо тепер доступне лише Premium\\-користувачам/Адміну.", reply_markup=None)
            await callback.answer("Комбо деактивовано!")
            await asyncio.sleep(1)
            await admin_menu_handler(callback.message)
            return
            
        elif callback.data == "status_info":
            await callback.answer(f"Комбо зараз: {'АКТИВНО' if IS_ACTIVE else 'НЕАКТИВНО'}")
            return
            
        elif callback.data == "admin_menu":
            await callback.answer("Відкриваю адмін-меню...")
            await admin_menu_handler(callback.message)
            return

    # Обробка кнопки "Отримати Premium" (для звичайних користувачів)
    if callback.data == "get_premium":
        await callback.answer("Переадресація на оплату...", show_alert=False)
        
        # 1. Створення інвойсу через Crypto Bot API
        try:
            # Для цього прикладу, ми не знаємо BOT_USERNAME, тому передаємо 0
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
                await callback.message.answer("⚠️ Не вдалося створити платіжний інвойс. Спробуйте пізніше.")
                
        except Exception as e:
            logging.error(f"Помилка створення інвойсу: {e}")
            await callback.message.answer("❌ Сталася помилка при підключенні до платіжної системи.")
            
# Обробка кнопки "Я сплатив"
@F.callback_query.data.startswith("check_payment_")
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
                    "🎉 **Оплата успішна!** Ви отримали Premium\\-доступ\\.\n"
                    "Надішліть `/combo` для отримання актуальних кодів\\."
                )
                await callback.answer("Підписка активована!", show_alert=True)
                # Тут мала б бути логіка збереження підписки у базу даних
                return
            
            elif status == 'pending':
                await callback.answer("Платіж ще обробляється. Спробуйте через хвилину.")
                return
            
            elif status == 'expired':
                await callback.message.edit_text(
                    "❌ **Термін дії інвойсу сплив.** Будь ласка, створіть новий інвойс для оплати\\."
                )
                await callback.answer("Термін дії сплив.", show_alert=True)
                return
                
            else: # refunded, failed
                await callback.message.answer("Статус платежу: " + status)
        
        else:
            await callback.answer("Не вдалося отримати статус інвойсу. Зверніться до адміністратора.")
            
    except Exception as e:
        logging.error(f"Помилка перевірки статусу платежу: {e}")
        await callback.answer("❌ Сталася помилка при перевірці платежу.", show_alert=True)


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
    """Головна функція запуску бота."""
    bot = setup_bot()
    dp = Dispatcher()

    # Реєстрація всіх хендлерів
    dp.include_routers(
        dp.message.register(command_start_handler, CommandStart()),
        dp.message.register(command_combo_handler, Command("combo")),
        dp.message.register(admin_menu_handler, Command("admin_menu")),
        dp.callback_query.register(inline_callback_handler, F.callback_query.data.in_({"get_premium", "admin_menu", "activate_combo", "deactivate_combo", "status_info"})),
        dp.callback_query.register(check_payment_handler, F.callback_query.data.startswith("check_payment_"))
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
