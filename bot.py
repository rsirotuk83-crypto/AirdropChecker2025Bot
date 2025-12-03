import os
import asyncio
import httpx # Import для асинхронних HTTP-запитів до Crypto Bot API
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.filters import CommandStart, Command

# Ініціалізуємо диспетчер ГЛОБАЛЬНО, щоб хендлери могли його знайти
dp = Dispatcher()

# --- 1. КОНСТАНТИ ТА КОНФІГУРАЦІЯ ---

# Отримання токенів з системних змінних Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN") # Токен для Crypto Bot API
ADMIN_ID = os.getenv("ADMIN_ID") # ID адміністратора для управління преміумом

# Конфігурація платежів
PAYMENT_AMOUNT = "1.00" # Сума платежу (наприклад, 1.00 USD)
CURRENCY = "USD"
PAYMENT_ASSET = "USDT" # Використовуйте USDT для стабільності
PAYMENT_INVOICE_URL = "https://pay.crypt.bot/api/createInvoice"
PAYMENT_CHECK_URL = "https://pay.crypt.bot/api/getInvoices"
INVOICE_DESCRIPTION = "Преміум доступ до комбо-кодів на 30 днів"

# Текст повного комбо (Сховано за преміумом)
FULL_COMBO_TEXT = (
    "⭐️ **Комбо та коди на {date} (PREMIUM)** ⭐️\n\n"
    "💰 **ВСІ АКТУАЛЬНІ КОМБО-КОДИ (оновлення кожні 24 години)**:\n\n"
    "1. **Hamster Kombat** → Pizza → Wallet → Rocket 🚀\n"
    "2. **Blum** → Cipher: FREEDOM 🔐\n"
    "3. **TapSwap** → MATRIX 🟢\n"
    "4. **CATS** → MEOW2025 🐱\n"
    "5. **Rocky Rabbit** → 3→1→4→2 🐰\n"
    "6. **Yescoin** → ↑→↓← 🟡\n"
    "7. **DOGS** → DOGS2025 🐶\n"
    "8. **PixelTap** → FIRE 🔥\n"
    "9. **W-Coin** → A→B→C→D 🪙\n"
    "10. **MemeFi** → LFG 🐸\n"
    "11. **DotCoin** → PRO \n"
    "12. **BountyBot** → BTC \n"
    "13. **NEAR Wallet** → BONUS \n"
    "14. **Hot Wallet** → MOON \n"
    "15. **Avagold** → GOLD \n"
    "16. **CEX.IO** → STAKE \n"
    "17. **Pocketfi** → POCKET \n"
    "18. **Seedify** → SEED \n"
    "19. **QDROP** → AIRDROP \n"
    "20. **MetaSense** → MET \n"
    "21. **SQUID** → FISH 🐟\n\n"
    "***+ ще 5-7 рідкісних комбо щодня...***"
)

# --- 2. СЛОВНИКИ ТА БАЗА ДАНИХ (для прикладу - в пам'яті) ---

# База даних користувачів (UserID: {'lang': 'ua', 'premium_expiry': datetime_object or None, 'bot_username': str})
user_data = {}

# Тексти для багатомовності
TEXTS = {
    'ua': {
        'welcome': "Привіт! Я твій бот для щоденних комбо-кодів та шифрів для найпопулярніших крипто-тапалок.\n\n**Обери мову, або натисни /combo, щоб почати!**",
        'lang_changed': "✅ Мову змінено на українську.",
        'combo_free': "🔒 **Сьогоднішнє комбо**\n\nЦей розділ доступний тільки для Premium користувачів. Отримайте **ранній доступ** до комбо-кодів для 20+ ігор лише за **{amount} {currency}** на місяць!",
        'combo_premium': FULL_COMBO_TEXT,
        'premium_active': "✅ **PREMIUM АКТИВОВАНО!**\n\nВаша підписка діє до: **{expiry_date} (UTC)**.\nОсь ваше сьогоднішнє комбо 👇",
        'buy_button': f"💳 Придбати Premium ({PAYMENT_AMOUNT} {CURRENCY} / 30 днів)",
        'check_button': "✅ Я оплатив (Перевірити платіж)",
        'checking': "⏱️ Перевіряю статус вашого платежу... Це може зайняти кілька секунд.",
        'paid_success': "🎉 **Оплата успішна!**\n\nВашу підписку активовано на 30 днів! Дякую за підтримку. Отримайте ваше комбо, натиснувши /combo.",
        'paid_fail': "❌ **Платіж не знайдено або він не завершений.**\n\nБудь ласка, переконайтеся, що ви надіслали {amount} {currency} на інвойс, і повторіть спробу. Якщо проблема не зникає, зв'яжіться з адміністратором.",
        'admin_activated': "✅ **Преміум активовано** для {user_id} до {expiry_date}.",
        'admin_deactivated': "✅ **Преміум деактивовано** для {user_id}.",
        'admin_only': "❌ Ця команда доступна лише адміністратору.",
        'usage_admin': "Використання:\n`/activate <UserID>`\n`/deactivate <UserID>`",
    },
    'ru': {
        'welcome': "Привет! Я твой бот для ежедневных комбо-кодов и шифров для самых популярных крипто-тапалок.\n\n**Выбери язык, или нажми /combo, чтобы начать!**",
        'lang_changed': "✅ Язык изменен на русский.",
        'combo_free': "🔒 **Сегодняшнее комбо**\n\nЭтот раздел доступен только для Premium пользователей. Получите **ранний доступ** к комбо-кодам для 20+ игр всего за **{amount} {currency}** в месяц!",
        'combo_premium': FULL_COMBO_TEXT.replace('Комбо та коди', 'Комбо и коды').replace('сьогоднішнє', 'сегодняшнее'),
        'premium_active': "✅ **PREMIUM АКТИВИРОВАН!**\n\nВаша подписка действует до: **{expiry_date} (UTC)**.\nВот ваше сегодняшнее комбо 👇",
        'buy_button': f"💳 Купить Premium ({PAYMENT_AMOUNT} {CURRENCY} / 30 дней)",
        'check_button': "✅ Я оплатил (Проверить платеж)",
        'checking': "⏱️ Проверяю статус вашего платежа... Это может занять несколько секунд.",
        'paid_success': "🎉 **Оплата успешна!**\n\nВаша подписка активирована на 30 дней! Спасибо за поддержку. Получите ваше комбо, нажав /combo.",
        'paid_fail': "❌ **Платеж не найден или не завершен.**\n\nПожалуйста, убедитесь, что вы отправили {amount} {currency} на инвойс, и повторите попытку. Если проблема не исчезает, свяжитесь с администратором.",
        'admin_activated': "✅ **Премиум активирован** для {user_id} до {expiry_date}.",
        'admin_deactivated': "✅ **Премиум деактивирован** для {user_id}.",
        'admin_only': "❌ Эта команда доступна только администратору.",
        'usage_admin': "Использование:\n`/activate <UserID>`\n`/deactivate <UserID>`",
    }
}

# --- 3. УТИЛІТАРНІ ФУНКЦІЇ ДЛЯ БАЗИ ДАНИХ ---

def get_user_lang(user_id):
    """Отримує мову користувача, за замовчуванням - UA."""
    return user_data.get(user_id, {}).get('lang', 'ua')

def get_text(user_id, key, **kwargs):
    """Повертає текст на потрібній мові з динамічними параметрами."""
    lang = get_user_lang(user_id)
    text = TEXTS.get(lang, TEXTS['ua']).get(key, f"Error: Key '{key}' not found.")
    return text.format(**kwargs)

def is_premium(user_id):
    """Перевіряє, чи активна преміум підписка."""
    user = user_data.get(user_id)
    if not user or 'premium_expiry' not in user or not user['premium_expiry']:
        return False
    
    return user['premium_expiry'] > datetime.now()

def activate_premium(user_id):
    """Активація преміум-підписки на 30 днів."""
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'ua', 'premium_expiry': None}

    # Підписка на 30 днів, як ви просили
    expiry_date = datetime.now() + timedelta(days=30)
    user_data[user_id]['premium_expiry'] = expiry_date
    return expiry_date.strftime("%Y-%m-%d %H:%M:%S")

def deactivate_premium(user_id):
    """Деактивація преміум-підписки."""
    if user_id in user_data:
        user_data[user_id]['premium_expiry'] = None

# --- 4. ФУНКЦІЇ ДЛЯ ВЗАЄМОДІЇ З CRYPTO BOT API ---

async def create_invoice(user_id, bot_username):
    """Створює інвойс через Crypto Bot API."""
    try:
        # Використовуємо кастомний payload для ідентифікації користувача та перевірки
        payload = {
            "asset": PAYMENT_ASSET,
            "amount": PAYMENT_AMOUNT,
            "description": INVOICE_DESCRIPTION,
            "paid_btn_name": "callback",
            # Використовуємо bot_username, отриманий під час запуску
            "paid_btn_url": f"t.me/{bot_username}?start=check_payment_{user_id}", 
            "payload": f"combo_access_{user_id}", # Кастомний payload для ідентифікації
            "allow_anonymous": True,
            "allow_comments": False,
            "fiat": CURRENCY
        }
        
        headers = {
            "X-App-Token": CRYPTO_BOT_TOKEN
        }
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(PAYMENT_INVOICE_URL, headers=headers, json=payload)
            response.raise_for_status() # Викликає виняток для HTTP-помилок
            data = response.json()
            
            if data['ok'] and data['result']:
                return data['result']['pay_url'], data['result']['invoice_id']
            
            print(f"Crypto Bot API Error: {data}")
            return None, None
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP error creating invoice: {e.response.status_code} - {e.response.text}")
        return None, None
    except Exception as e:
        print(f"Error creating invoice: {e}")
        return None, None

async def check_invoice(invoice_id):
    """Перевіряє статус інвойсу через Crypto Bot API."""
    try:
        params = {
            "invoice_ids": invoice_id
        }
        headers = {
            "X-App-Token": CRYPTO_BOT_TOKEN
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(PAYMENT_CHECK_URL, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['ok'] and data['result']:
                # Перевіряємо статус першого (і єдиного) інвойсу
                invoice = data['result']['items'][0]
                return invoice['status'] == 'paid' # True, якщо оплачено
            
            print(f"Crypto Bot API Check Error: {data}")
            return False
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP error checking invoice: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e:
        print(f"Error checking invoice: {e}")
        return False

# --- 5. ОБРОБНИКИ (HANDLERS) ---

# Обробник команди /start
@dp.message(CommandStart())
async def command_start_handler(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    
    # Ініціалізація даних користувача, якщо він новий
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'ua', 'premium_expiry': None}

    # Кнопки вибору мови
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="set_lang_ua")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru")],
        [InlineKeyboardButton(text="🔑 /combo", callback_data="show_combo")],
    ])

    await message.answer(get_text(user_id, 'welcome'), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

# Обробник команди /combo та натискання кнопки "Сьогоднішнє комбо"
@dp.message(Command("combo"))
@dp.callback_query(F.data == "show_combo")
async def show_combo_handler(callback_or_message, bot: Bot):
    
    if isinstance(callback_or_message, Message):
        message = callback_or_message
    else:
        message = callback_or_message.message
        await callback_or_message.answer() # Прибираємо годинник з кнопки

    user_id = message.chat.id
    lang = get_user_lang(user_id)
    
    # Отримуємо username бота з конфігурації (додано в main)
    bot_username = bot.config.bot_username 
    if not bot_username:
         # Це має бути визначено в main(), але як запасний варіант
         bot_info = await bot.get_me()
         bot_username = bot_info.username


    if is_premium(user_id):
        # Premium: показуємо повний текст
        expiry_date = user_data[user_id]['premium_expiry'].strftime("%Y-%m-%d %H:%M:%S")
        text = get_text(user_id, 'premium_active', expiry_date=expiry_date)
        combo_text = get_text(user_id, 'combo_premium', date=datetime.now().strftime("%d.%m.%Y"))
        
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)
        await message.answer(combo_text, parse_mode=ParseMode.MARKDOWN)

    else:
        # Free: пропонуємо купити
        # Передаємо bot_username, щоб функція створення інвойсу не покладалася на get_current()
        pay_url, invoice_id = await create_invoice(user_id, bot_username) 

        if not pay_url:
            await message.answer("❌ **Виникла помилка** при створенні інвойсу. Спробуйте пізніше.")
            return

        # Зберігаємо invoice_id для подальшої перевірки (для простоти - в data)
        if user_id not in user_data:
            user_data[user_id] = {'lang': lang, 'premium_expiry': None, 'invoice_id': invoice_id}
        else:
            user_data[user_id]['invoice_id'] = invoice_id


        # Клавіатура з посиланням на оплату та кнопкою перевірки
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text(user_id, 'buy_button'), url=pay_url)],
            [InlineKeyboardButton(text=get_text(user_id, 'check_button'), callback_data=f"check_payment_{invoice_id}")]
        ])
        
        text = get_text(user_id, 'combo_free', amount=PAYMENT_AMOUNT, currency=CURRENCY)
        await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

# Обробник кнопки перевірки платежу
@dp.callback_query(F.data.startswith("check_payment_"))
async def check_payment_callback(callback: types.CallbackQuery):
    await callback.answer(get_text(callback.from_user.id, 'checking'))

    invoice_id = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    
    # 1. Перевіряємо статус інвойсу через Crypto Bot API
    is_paid = await check_invoice(invoice_id)
    
    if is_paid:
        # 2. Якщо оплачено, активуємо підписку
        expiry_date = activate_premium(user_id)
        
        # 3. Редагуємо повідомлення, щоб повідомити про успіх
        try:
            await callback.message.edit_text(
                get_text(user_id, 'paid_success'),
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            # Якщо повідомлення занадто старе, просто надсилаємо нове
            await callback.message.answer(
                get_text(user_id, 'paid_success'),
                parse_mode=ParseMode.MARKDOWN
            )
        
    else:
        # 4. Якщо не оплачено, повідомляємо користувача
        await callback.message.answer(
            get_text(user_id, 'paid_fail', amount=PAYMENT_AMOUNT, currency=CURRENCY),
            parse_mode=ParseMode.MARKDOWN
        )

# Обробник вибору мови
@dp.callback_query(F.data.startswith("set_lang_"))
async def set_language_handler(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {'lang': lang_code, 'premium_expiry': None}
    else:
        user_data[user_id]['lang'] = lang_code
    
    await callback.message.edit_text(get_text(user_id, 'lang_changed'), reply_markup=None)
    await callback.answer(get_text(user_id, 'lang_changed'))


# --- 6. АДМІН-КОМАНДИ ---

@dp.message(Command("activate"))
async def admin_activate_handler(message: Message):
    if str(message.from_user.id) != ADMIN_ID:
        await message.answer(get_text(message.from_user.id, 'admin_only'))
        return

    args = message.text.split()
    if len(args) != 2:
        await message.answer(get_text(message.from_user.id, 'usage_admin'))
        return

    target_user_id_str = args[1]
    try:
        target_user_id = int(target_user_id_str)
        expiry_date = activate_premium(target_user_id)
        await message.answer(get_text(message.from_user.id, 'admin_activated', user_id=target_user_id, expiry_date=expiry_date))
    except ValueError:
        await message.answer("❌ Невірний формат UserID. Це має бути число.")

@dp.message(Command("deactivate"))
async def admin_deactivate_handler(message: Message):
    if str(message.from_user.id) != ADMIN_ID:
        await message.answer(get_text(message.from_user.id, 'admin_only'))
        return

    args = message.text.split()
    if len(args) != 2:
        await message.answer(get_text(message.from_user.id, 'usage_admin'))
        return

    target_user_id_str = args[1]
    try:
        target_user_id = int(target_user_id_str)
        deactivate_premium(target_user_id)
        await message.answer(get_text(message.from_user.id, 'admin_deactivated', user_id=target_user_id))
    except ValueError:
        await message.answer("❌ Невірний формат UserID. Це має бути число.")

# --- 7. ЗАПУСК БОТА ---

async def main() -> None:
    # Перевірка наявності токенів
    if not BOT_TOKEN or not CRYPTO_BOT_TOKEN:
        print("ПОМИЛКА: Не встановлено BOT_TOKEN або CRYPTO_BOT_TOKEN в змінних середовища.")
        return
    if not ADMIN_ID:
        print("УВАГА: Не встановлено ADMIN_ID. Адмін-команди не працюватимуть.")

    # Створюємо екземпляр бота з правильним режимом парсингу
    bot = Bot(BOT_TOKEN, parse_mode=ParseMode.MARKDOWN) 
    
    # Отримуємо та зберігаємо username бота в його конфігурації
    # Це необхідно для коректного формування paid_btn_url в інвойсі
    try:
        bot_info = await bot.get_me()
        bot.config.bot_username = bot_info.username
        print(f"Бот @{bot.config.bot_username} запущено. Починаю обробку оновлень...")
    except Exception as e:
        print(f"ПОМИЛКА: Не вдалося отримати інформацію про бота. Перевірте BOT_TOKEN. Помилка: {e}")
        return

    # Запуск обробки всіх вхідних оновлень (обов'язково передаємо об'єкт bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        # Змінюємо asyncio.run, щоб він не приховував помилки
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинено вручну.")
    except Exception as e:
        print(f"Непередбачена помилка в основній функції: {e}")
