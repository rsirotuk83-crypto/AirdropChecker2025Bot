import os
import asyncio
import json
from datetime import datetime, timedelta
import logging

# --- aiogram 3.x імпорти ---
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
# -------------------------------------------------

# Налаштування логування для відстеження роботи на Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Отримання токена з оточення Railway
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN environment variable not set. Railway deployment will fail without it.")
    
# Ініціалізація бота та диспетчера
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Файли для зберігання даних
LANG_FILE = "lang.json"
# Змінено PAID_FILE на JSON для зберігання дати закінчення підписки
PREMIUM_USERS_FILE = "premium_users.json" 

# ─── ПЕРЕКЛАДИ ─────────────────────
TEXTS = {
    "uk": {"flag": "🇺🇦", "name": "Українська", "start": "Привіт! @CryptoComboDaily\nВсі комбо та коди 20+ тапалок в одному місці\n\nОбери мову:",
           "set": "Мову змінено на українську ✅",
           "btn": "Сьогоднішні комбо",
           "combo_header": "Комбо та коди на",
           "premium_text": "\n\n<b>ПОВНИЙ ДОСТУП:</b>\n\n🟢 <b>Преміум 1$/міс</b> — ранній доступ + всі коди (20+ ігор).",
           "premium_active": "Преміум активовано на місяць! ✅"
           },
    "ru": {"flag": "🇷🇺", "name": "Русский", "start": "Привет! @CryptoComboDaily\nВсе комбо и коды 20+ тапалок в одном месте\n\nВыбери язык:",
           "set": "Язык изменён на русский ✅",
           "btn": "Сегодняшние комбо",
           "combo_header": "Комбо и коды на",
           "premium_text": "\n\n<b>ПОЛНЫЙ ДОСТУП:</b>\n\n🟢 <b>Премиум 1$/мес</b> — ранний доступ + все коды (20+ игр).",
           "premium_active": "Премиум активирован на месяц! ✅"
           },
    "en": {"flag": "🇬🇧", "name": "English", "start": "Hey! @CryptoComboDaily\nAll combos & codes for 20+ tap games\n\nChoose language:",
           "set": "Language set to English ✅",
           "btn": "Today's combos",
           "combo_header": "Combos & codes for",
           "premium_text": "\n\n<b>FULL ACCESS:</b>\n\n🟢 <b>Premium $1/mo</b> — early access + all codes (20+ games).",
           "premium_active": "Premium activated for one month! ✅"
           },
    "es": {"flag": "🇪🇸", "name": "Español", "start": "¡Hola! @CryptoComboDaily\nTodos los combos y códigos de 20+ tap games\n\nElige idioma:",
           "set": "Idioma cambiado a español ✅",
           "btn": "Combos de hoy",
           "combo_header": "Combos de hoy",
           "premium_text": "\n\n<b>ACCESO COMPLETO:</b>\n\n🟢 <b>Premium $1/mes</b> — acceso anticipado + todos los códigos (20+ juegos).",
           "premium_active": "Premium activado por un mes! ✅"
           },
    "de": {"flag": "🇩🇪", "name": "Deutsch", "start": "Hallo! @CryptoComboDaily\nAlle Combos & Codes von 20+ Tap-Games\n\nSprache wählen:",
           "set": "Sprache auf Deutsch geändert ✅",
           "btn": "Heutige Combos",
           "combo_header": "Heutige Combos",
           "premium_text": "\n\n<b>VOLLER ZUGRIFF:</b>\n\n🟢 <b>Premium 1$/Monat</b> — Frühzugriff + alle Codes (20+ Spiele).",
           "premium_active": "Premium für einen Monat aktiviert! ✅"
           }
}

# ─── КОМБО-КОДИ ─────────────────────

# Повний список комбо-кодів (для преміум)
FULL_COMBO_TEXT = (
    "Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
    "Blum → Cipher: FREEDOM\n"
    "TapSwap → MATRIX\n"
    "CATS → MEOW2025\n"
    "Rocky Rabbit → 3→1→4→2\n"
    "Yescoin → ←↑→↓←\n"
    "DOGS → DOGS2025\n"
    "PixelTap → FIRE 💥\n"
    "YesTap → WXYZ\n"
    "W-Coin → A→B→C→D\n"
    "MemeFi → LFG\n"
    "DotCoin → PRO\n"
    "BountyBot → BTC\n"
    "NEAR Wallet → BONUS\n"
    "Hot Wallet → MOON\n"
    "Avagold → GOLD\n"
    "CEX.IO → STAKE\n"
    "Pocketfi → POCKET\n"
    "Seedify → SEED\n"
    "QDROP → AIRDROP\n"
    "MetaSense → MET\n"
    "SQUID → FISH\n"
    "+ ще 5-7 рідкісних комбо..."
)

# Демо-список комбо-кодів (для безкоштовного доступу)
DEMO_COMBO_TEXT = (
    "Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
    "Blum → Cipher: FREEDOM\n"
    "TapSwap → MATRIX\n"
    "CATS → MEOW2025\n"
    "Rocky Rabbit → 3→1→4→2\n"
    "Yescoin → ←↑→↓←\n"
    "DOGS → DOGS2025\n"
    "..."
)

# --- ФУНКЦІЇ РОБОТИ З ФАЙЛАМИ (LANG) ---

def get_lang(uid):
    """Отримує обрану мову користувача (за замовчуванням 'uk')."""
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return data.get(str(uid), "uk")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Помилка читання або декодування {LANG_FILE}: {e}")
            return "uk"
    return "uk"

def save_lang(uid, lang):
    """Зберігає обрану мову користувача."""
    data = {}
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (IOError, json.JSONDecodeError):
            logger.warning(f"Файл {LANG_FILE} пошкоджений або порожній. Створюємо новий.")
            pass
            
    data[str(uid)] = lang
    try:
        with open(LANG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False) 
    except IOError as e:
        logger.error(f"Помилка запису в файл {LANG_FILE}: {e}")

# --- ФУНКЦІЇ РОБОТИ З ФАЙЛАМИ (PREMIUM) ---

def get_premium_users():
    """Читає дані про преміум-користувачів із датою закінчення підписки."""
    if os.path.exists(PREMIUM_USERS_FILE):
        try:
            with open(PREMIUM_USERS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Помилка читання або декодування {PREMIUM_USERS_FILE}: {e}")
            # Повертаємо порожній словник у разі помилки, щоб не заблокувати бота
            return {}
    return {}

def save_premium_users(data):
    """Зберігає дані про преміум-користувачів."""
    try:
        with open(PREMIUM_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Помилка запису в файл {PREMIUM_USERS_FILE}: {e}")

def is_premium(uid):
    """Перевіряє, чи активна підписка у користувача."""
    users_data = get_premium_users()
    user_id = str(uid)
    
    if user_id in users_data:
        expiry_date_str = users_data[user_id]["expiry_date"]
        # Перетворюємо рядок дати назад у об'єкт datetime
        expiry_date = datetime.fromisoformat(expiry_date_str)
        
        # Якщо термін дії не закінчився, повертаємо True
        if expiry_date > datetime.now():
            return True
        else:
            # Термін дії закінчився, видаляємо запис для чистоти
            del users_data[user_id]
            save_premium_users(users_data)
            logger.info(f"Преміум користувача {user_id} закінчився і був видалений.")
            return False
            
    return False

# ─── КНОПКИ (Використовуємо прапори для кращого UX) ─────────────────────────
lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text=f"{TEXTS['uk']['flag']} {TEXTS['uk']['name']}", callback_data="lang_uk")],
    [types.InlineKeyboardButton(text=f"{TEXTS['ru']['flag']} {TEXTS['ru']['name']}", callback_data="lang_ru")],
    [types.InlineKeyboardButton(text=f"{TEXTS['en']['flag']} {TEXTS['en']['name']}", callback_data="lang_en")],
    [types.InlineKeyboardButton(text=f"{TEXTS['es']['flag']} {TEXTS['es']['name']}", callback_data="lang_es")],
    [types.InlineKeyboardButton(text=f"{TEXTS['de']['flag']} {TEXTS['de']['name']}", callback_data="lang_de")]
])

@dp.message(CommandStart())
async def start(msg: types.Message):
    """Обробник команди /start. Пропонує обрати мову."""
    l = get_lang(msg.from_user.id)
    await msg.answer(TEXTS[l]["start"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(cb: types.CallbackQuery):
    """Обробник вибору мови. Зберігає мову і змінює клавіатуру."""
    l = cb.data.split("_")[1]
    save_lang(cb.from_user.id, l)
    
    # Відправляємо Reply-клавіатуру з кнопкою "Сьогоднішні комбо"
    kb = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=TEXTS[l]["btn"])]], 
                                   resize_keyboard=True, 
                                   input_field_placeholder=TEXTS[l]["btn"])
    
    await cb.message.edit_text(TEXTS[l]["set"], reply_markup=None) 
    await cb.message.answer(TEXTS[l]["set"], reply_markup=kb) 
    await cb.answer(TEXTS[l]["set"])

@dp.message(F.text.func(lambda m: m in [TEXTS[x]["btn"] for x in TEXTS]))
async def combos(msg: types.Message):
    """Відправляє комбо-коди, надаючи повний список лише преміум-користувачам."""
    l = get_lang(msg.from_user.id)
    today_date = datetime.now().strftime('%d.%m.%Y')
    
    # Заголовок
    text = f"<b>{TEXTS[l]['combo_header']} {today_date}</b>\n\n"
    
    is_user_premium = is_premium(msg.from_user.id)
    
    if is_user_premium:
        # ПРЕМІУМ-КОРИСТУВАЧІ: Повний список
        text += FULL_COMBO_TEXT
        await msg.answer(text)
    else:
        # БЕЗКОШТОВНІ КОРИСТУВАЧІ: Демо-список + Пропозиція підписки
        text += DEMO_COMBO_TEXT
        
        # Клавіатура для неоплаченого користувача
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            # УВАГА: URL потрібно оновити на ваш реальний спосіб оплати!
            [types.InlineKeyboardButton(text="💳 Оплатити Преміум 1$", url="https://t.me/send?start=IVWQeJXKYVsd")],
            [types.InlineKeyboardButton(text="Я оплатив (Перевірити)", callback_data="paid")]
        ])
        
        text += TEXTS[l]["premium_text"]
        await msg.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "paid")
async def paid_check(cb: types.CallbackQuery):
    """
    Обробник кнопки "Я оплатив (Перевірити)". 
    Додає користувача до преміум-списку на 30 днів (імітація активації).
    """
    user_id = str(cb.from_user.id)
    users_data = get_premium_users()
    
    # Визначаємо дату закінчення підписки (сьогодні + 30 днів)
    expiry_date = datetime.now() + timedelta(days=30)
    
    # Зберігаємо дані у форматі JSON
    users_data[user_id] = {
        "expiry_date": expiry_date.isoformat(),
        "start_date": datetime.now().isoformat()
    }
    
    save_premium_users(users_data)
    
    # Визначаємо мову для відповіді
    l = get_lang(cb.from_user.id)
    
    await cb.message.edit_text(TEXTS[l]["premium_active"])
    await cb.answer("Підписка активована!")


@dp.message()
async def echo_handler(message: types.Message):
    """Обробник для будь-яких інших повідомлень, які не є командами чи кнопками."""
    l = get_lang(message.from_user.id)
    await message.answer(TEXTS[l]["start"], reply_markup=lang_kb)


async def main():
    logger.info("БОТ @CryptoComboDaily — 100% ЖИВИЙ")
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот зупинено вручну.")
    except Exception as e:
        logger.error(f"Критична помилка запуску: {e}")
