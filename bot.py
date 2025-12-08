import os
import asyncio
import logging
import json
import httpx
import re
from datetime import datetime

# ВАЖЛИВО: Імпортуємо необхідні компоненти для Webhooks та aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.methods import SetWebhook, DeleteWebhook
from aiohttp import web # Компонент веб-сервера

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Налаштування змінних середовища та конфігурація Webhook ---
# Railway автоматично надає ці змінні
BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# Webhook-специфічні змінні
# PORT - порт, який надає Railway.
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
# WEBHOOK_HOST - ваш домен, який надає Railway (наприклад, airdropchecker2025bot-production.up.railway.app)
# Якщо змінна WEBHOOK_HOST не встановлена, використовуємо заглушку.
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") or "https://airdropchecker2025bot-production.up.railway.app" 
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

if not BOT_TOKEN or not CRYPTO_BOT_TOKEN:
    logging.error("ПОМИЛКА: BOT_TOKEN або CRYPTO_BOT_TOKEN не встановлено.")
    exit(1)

try:
    # ADMIN_ID тепер може бути необов'язковим, якщо він відсутній, логіка запрацює
    if ADMIN_ID:
        ADMIN_ID = int(ADMIN_ID)
    else:
        logging.warning("ПОПЕРЕДЖЕННЯ: ADMIN_ID не встановлено. Адмін-функції не будуть доступні.")
        ADMIN_ID = 0 # Встановлюємо 0, щоб уникнути помилок типу
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

# --- Утиліти для екранування (Markdown V2) ---

def escape_all_except_formatting(text: str) -> str:
    """
    Екранує ВСІ спеціальні символи Markdown V2, крім тих, 
    що використовуються для необхідного форматування (** та `). 
    """
    
    # 1. Escape the backslash itself first
    text = text.replace('\\', r'\\') 

    # 2. Агресивне екранування всіх критичних символів, що не є маркерами форматування.
    for char in '.-:!(){}[]<>#+-=|~':
        text = text.replace(char, r'\\' + char)
    
    # Спеціальна обробка для підкреслення, яке є маркером курсиву
    # Екрануємо його, якщо воно не оточене текстом (що унеможливлює використання його як курсиву)
    text = text.replace('_', r'\_')

    return text


# --- Хелпери та Хендлери (без змін у логіці, але адаптовані для DP) ---

# Ініціалізація бота
def setup_bot():
    """Створює екземпляр бота з коректними налаштуваннями для aiogram 3.x."""
    bot_properties = DefaultBotProperties(
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    return Bot(token=BOT_TOKEN, default=bot_properties)

# Хелпер для Admin Menu
def _build_admin_menu_content():
    """Створює текст та клавіатуру для меню адміністратора."""
    global IS_ACTIVE
    
    status_text = r'**АКТИВНО**' if IS_ACTIVE else r'**НЕАКТИВНО**'
    
    if IS_ACTIVE:
        button_text = "🔴 Деактивувати комбо (Тільки для Premium)"
        callback = "deactivate_combo"
    else:
        button_text = "🟢 Активувати комбо (Доступно всім)"
        callback = "activate_combo"
        
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=button_text, callback_data=callback)],
        [types.InlineKeyboardButton(text="⬅️ Назад до /start", callback_data="back_to_start")]
    ])
    
    base_text = escape_all_except_formatting(
        f"⚙️ Панель адміністратора\n\n"
        f"Поточний стан відображення комбо для всіх користувачів: {status_text}\n\n"
        "Натисніть кнопку, щоб змінити стан."
    )
    
    text = base_text.replace(r'⚙️ Панель адміністратора', r'⚙️ \*\*Панель адміністратора\*\*')
    text = text.replace(r'\*\*АКТИВНО\*\*', r'**АКТИВНО**')
    text = text.replace(r'\*\*НЕАКТИВНО\*\*', r'**НЕАКТИВНО**')

    return text, keyboard

# Хелпер для /start 
def _build_start_message_content(user_name: str, user_id: int, is_admin: bool):
    """Створює текст та клавіатуру для початкового повідомлення /start."""
    global IS_ACTIVE
    
    escaped_user_name = escape_all_except_formatting(user_name)
    combo_status = r'**АКТИВНО**' if IS_ACTIVE else r'**НЕАКТИВНО**'
    status_text = ""
    keyboard = None
    
    if is_admin:
        status_text = escape_all_except_formatting(
            f"Ваш ID: `{user_id}`\nСтатус: Адміністратор\nАктивність: {combo_status}\n\n"
        )
        status_text = status_text.replace(r'Статус: Адміністратор', r'\*\*Статус\:\*\* Адміністратор')
        status_text = status_text.replace(r'Ваш ID:', r'\*\*Ваш ID\:\*\*')
        status_text = status_text.replace(r'Активність:', r'\*\*Активність\:\*\*')

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Управління активацією", callback_data="admin_menu")]
        ])
    else:
        status_text = escape_all_except_formatting(
            f"Ваш ID: `{user_id}`\n"
        )
        status_text = status_text.replace(r'Ваш ID:', r'\*\*Ваш ID\:\*\*')

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отримати Premium 🔑", callback_data="get_premium")],
        ])

    welcome_message = escape_all_except_formatting(
        f"👋 Привіт, {escaped_user_name}!\n\n"
        f"{status_text}"
        r"Цей бот надає ранній доступ до щоденних комбо та кодів для популярних криптоігор\.\n\n"
        r"Ціна Premium: 1 TON (або еквівалент)\."
    )

    welcome_message = welcome_message.replace(r'👋 Привіт,', r'👋 \*\*Привіт,\*\*')
    welcome_message = welcome_message.replace(r'Ціна Premium:', r'\*\*Ціна Premium\:\*\*')
    welcome_message = welcome_message.replace(r'\*\*АКТИВНО\*\*', r'**АКТИВНО**')
    welcome_message = welcome_message.replace(r'\*\*НЕАКТИВНО\*\*', r'**НЕАКТИВНО**')
    
    return welcome_message, keyboard


# Хендлер команди /start
async def command_start_handler(message: types.Message) -> None:
    """Обробляє команду /start і показує статус підписки."""
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    
    welcome_message, keyboard = _build_start_message_content(message.from_user.first_name, user_id, is_admin)
    
    await message.answer(welcome_message, reply_markup=keyboard)

# Хендлер команди /combo
async def command_combo_handler(message: types.Message) -> None:
    """Обробляє команду /combo."""
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    
    if is_admin or IS_ACTIVE:
        combo_text_raw = rf"""
📅 **Комбо та коди на {datetime.now().strftime(r'%d\.%m\.%Y')}**
*(Ранній доступ Premium)*
        
*Hamster Kombat* \u2192 Pizza \u2192 Wallet \u2192 Rocket
*Blum* \u2192 Cipher: FREEDOM
*TapSwap* \u2192 MATRIX
*CATS* \u2192 MEOW2025
*Rocky Rabbit* \u2192 3\u21921\u21924\u21922
*Yescoin* \u2192 \u2191\u2192\u2193\u2192\u2191
*DOGS* \u2192 DOGS2025
*PixelTap* \u2192 FIRE ✨
*W\-Coin* \u2192 A\u2192B\u2192C\u2192D
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
        
**\+ ще 5\-7 рідкісних комбо\.\.\.**
        """
        
        combo_text = combo_text_raw.replace('\u2192', r' \u2192 ').replace('\u2191', r'\u2191').replace('\u2193', r'\u2193')
        final_combo_text = escape_all_except_formatting(combo_text)
        final_combo_text = final_combo_text.replace(r'**\+ ще 5\\-\-7 рідкісних комбо\\.\.\\.\.\\\*\*', r'**\+ ще 5\-7 рідкісних комбо\.\.\.**')
        
        await message.answer(final_combo_text)
    else:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отримати Premium 🔑", callback_data="get_premium")],
        ])
        
        premium_message_raw = r"🔒 **Увага\!** Щоб отримати актуальні комбо та коди, вам потрібна Premium\-підписка\.\n\nНатисніть кнопку нижче, щоб оформити ранній доступ\." 
        premium_message = escape_all_except_formatting(premium_message_raw)
        premium_message = premium_message.replace(r'\*\*Увага\!\*\*', r'**Увага\!**')
        
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
async def inline_callback_handler(callback: types.CallbackQuery):
    """Обробляє натискання Inline-кнопок."""
    global IS_ACTIVE
    user_id = callback.from_user.id
    
    if user_id == ADMIN_ID:
        
        if callback.data == "back_to_start":
            welcome_message, keyboard = _build_start_message_content(callback.from_user.first_name, user_id, True)
            await callback.answer("Повернення до головного меню...")
            await callback.message.edit_text(welcome_message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
            return
            
        if callback.data == "activate_combo":
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

    if callback.data == "get_premium":
        await callback.answer("Переадресація на оплату...", show_alert=False)
        
        try:
            # Оскільки ми на Webhooks, ми можемо отримати username бота для посилання paid_btn_url
            bot_info = await callback.bot.get_me()
            bot_username = bot_info.username
            invoice_data = await create_invoice_request(callback.from_user.id, bot_username=bot_username)
            
            if invoice_data and invoice_data.get('ok') and invoice_data['result']['pay_url']:
                pay_url = invoice_data['result']['pay_url']
                invoice_id = invoice_data['result']['invoice_id']
                
                keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="Сплатити (Crypto Bot)", url=pay_url)],
                    [types.InlineKeyboardButton(text="Я сплатив 💸", callback_data=f"check_payment_{invoice_id}")]
                ])
                
                payment_message_raw = r"💰 **Оплата Premium**\n\nДля отримання раннього доступу сплатіть 1 TON (або еквівалент)\.\nНатисніть кнопку 'Сплатити' і після оплати — 'Я сплатив 💸'\."
                payment_message = escape_all_except_formatting(payment_message_raw)
                payment_message = payment_message.replace(r'\*\*Оплата Premium\*\*', r'**Оплата Premium**')
                
                await callback.message.answer(payment_message, reply_markup=keyboard)
            else:
                await callback.message.answer(r"⚠️ Не вдалося створити платіжний інвойс\. Спробуйте пізніше\.")
                
        except Exception as e:
            logging.error(f"Помилка створення інвойсу: {e}")
            await callback.message.answer(r"❌ Сталася помилка при підключенні до платіжної системи\.")
            
# Обробка кнопки "Я сплатив"
async def check_payment_handler(callback: types.CallbackQuery):
    """Перевірка статусу платежу через API Crypto Bot."""
    invoice_id = callback.data.split('_')[-1]
    
    try:
        payment_info = await check_invoice_status(invoice_id)
        
        if payment_info and payment_info.get('ok'):
            status = payment_info['result']['status']
            
            if status == 'paid':
                await callback.message.edit_text(
                    r"🎉 **Оплата успішна\!** Ви отримали Premium\-доступ\.\n"
                    r"Надішліть `\/combo` для отримання актуальних кодів\.",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                await callback.answer("Підписка активована!", show_alert=True)
                return
            
            elif status == 'pending':
                await callback.answer(r"Платіж ще обробляється\. Спробуйте через хвилину\.")
                return
            
            elif status == 'expired':
                await callback.message.edit_text(
                    r"❌ **Термін дії інвойсу сплив\.** Будь ласка, створіть новий інвойс для оплати\.",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                await callback.answer(r"Термін дії сплив\.", show_alert=True)
                return
                
            else: # refunded, failed
                await callback.message.answer("Статус платежу: " + escape_all_except_formatting(status))
        
        else:
            await callback.answer(r"Не вдалося отримати статус інвойсу\. Зверніться до адміністратора\.")
            
    except Exception as e:
        logging.error(f"Помилка перевірки статусу платежу: {e}")
        await callback.answer(r"❌ Сталася помилка при перевірці платежу\.", show_alert=True)


# --- HTTP запити до Crypto Bot API (Залишаються без змін) ---

async def create_invoice_request(user_id: int, bot_username: str):
    """Створює інвойс на 1 TON через Crypto Bot API."""
    url = f"{CRYPTO_BOT_API_URL}/createInvoice"
    
    is_testnet = os.getenv("IS_TESTNET", "false").lower() == "true"
    
    payload = {
        "asset": "TON",
        "amount": "1",
        "description": "Ранній доступ до Crypto Combo/Кодів",
        "hidden_message": f"User ID: {user_id}",
        "paid_btn_name": "callback",
        "paid_btn_url": f"t.me/{bot_username}", 
        "allow_anonymous": False,
        "payload": json.dumps({"user_id": user_id}),
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
                raise e

async def check_invoice_status(invoice_id: str):
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
                raise e

# --- Запуск бота (Webhook) ---

async def set_commands(bot: Bot):
    """Встановлює список команд для бота."""
    commands = [
        BotCommand(command="/start", description="Головне меню"),
        BotCommand(command="/combo", description="Отримати щоденне комбо"),
    ]
    await bot.set_my_commands(commands)
    
async def on_startup(bot: Bot):
    """Функція, що виконується під час запуску веб-сервера."""
    await set_commands(bot)
    
    # Встановлюємо Webhook
    logging.info(f"Встановлення Webhook на: {WEBHOOK_URL}")
    await bot.set_webhook(url=WEBHOOK_URL)
    
    # Також переконайтеся, що старі Webhook-и видалено, якщо ви раніше використовували Polling
    # Це є частиною on_startup, але set_webhook зазвичай це робить
    # await bot.delete_webhook()
    
    logging.info(f"WEBHOOK УСПІШНО ВСТАНОВЛЕНО та запущено на порту {WEB_SERVER_PORT}")


async def on_shutdown(bot: Bot):
    """Функція, що виконується під час завершення роботи веб-сервера."""
    # Рекомендовано видаляти Webhook при завершенні роботи
    await bot.delete_webhook()
    logging.info("Webhook видалено. Бот зупинено.")

async def main() -> None:
    """Головна функція запуску бота (в режимі Webhook)."""
    bot = setup_bot()
    dp = Dispatcher()

    # Реєстрація хендлерів (залишається без змін)
    dp.message.register(command_start_handler, CommandStart())
    dp.message.register(command_combo_handler, Command("combo"))
    dp.message.register(admin_menu_handler, Command("admin_menu"), F.from_user.id == ADMIN_ID)
    
    dp.callback_query.register(
        inline_callback_handler, 
        F.data.in_({"get_premium", "admin_menu", "activate_combo", "deactivate_combo", "status_info", "back_to_start"})
    )
    dp.callback_query.register(
        check_payment_handler, 
        F.data.startswith("check_payment_")
    )

    # Прив'язка функцій on_startup та on_shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запускаємо Webhook
    # Webhook-и aiogram використовують aiohttp для запуску веб-сервера
    web_app = web.Application()
    web_app.add_routes([
        web.post(WEBHOOK_PATH, dp) # Обробляє всі вхідні POST запити від Telegram
    ])

    # Запускаємо aiohttp веб-сервер
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEB_SERVER_PORT)
    
    logging.info(f"Запуск Webhook-сервера на http://0.0.0.0:{WEB_SERVER_PORT}")
    await site.start()

    # Залишаємось у цьому циклі, щоб програма не завершилася
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        # aiogram 3.x і aiohttp вимагають asyncio.run
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот зупинено вручну.")
    except Exception as e:
        logging.critical(f"Критична помилка при запуску Webhook: {e}")
