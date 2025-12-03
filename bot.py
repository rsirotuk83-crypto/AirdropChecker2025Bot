import os
import asyncio
import json
from datetime import datetime
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
    # Критична перевірка токена
    raise ValueError("TOKEN environment variable not set. Railway deployment will fail without it.")
    
# Ініціалізація бота та диспетчера
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Файли для зберігання даних
LANG_FILE = "lang.json"
PAID_FILE = "paid.txt"

# ─── ПЕРЕКЛАДИ ─────────────────────
TEXTS = {
    "uk": {"flag": "🇺🇦", "name": "Українська", "start": "Привіт! @CryptoComboDaily\nВсі комбо та коди 20+ тапалок в одному місці\n\nОбери мову:",
           "set": "Мову змінено на українську ✅",
           "btn": "Сьогоднішні комбо"},
    "ru": {"flag": "🇷🇺", "name": "Русский", "start": "Привет! @CryptoComboDaily\nВсе комбо и коды 20+ тапалок в одном месте\n\nВыбери язык:",
           "set": "Язык изменён на русский ✅",
           "btn": "Сегодняшние комбо"},
    "en": {"flag": "🇬🇧", "name": "English", "start": "Hey! @CryptoComboDaily\nAll combos & codes for 20+ tap games\n\nChoose language:",
           "set": "Language set to English ✅",
           "btn": "Today's combos"},
    "es": {"flag": "🇪🇸", "name": "Español", "start": "¡Hola! @CryptoComboDaily\nTodos los combos y códigos de 20+ tap games\n\nElige idioma:",
           "set": "Idioma cambiado a español ✅",
           "btn": "Combos de hoy"},
    "de": {"flag": "🇩🇪", "name": "Deutsch", "start": "Hallo! @CryptoComboDaily\nAlle Combos & Codes von 20+ Tap-Games\n\nSprache wählen:",
           "set": "Sprache auf Deutsch geändert ✅",
           "btn": "Heutige Combos"}
}

# --- ФУНКЦІЇ РОБОТИ З ФАЙЛАМИ (Надійна обробка помилок) ---

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
            # Використовуємо ensure_ascii=False для коректного запису кирилиці
            json.dump(data, f, indent=4, ensure_ascii=False) 
    except IOError as e:
        logger.error(f"Помилка запису в файл {LANG_FILE}: {e}")


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
    
    # Редагуємо повідомлення з Inline-клавіатурою
    await cb.message.edit_text(TEXTS[l]["set"], reply_markup=None) # Видаляємо Inline-кнопки
    await cb.message.answer(TEXTS[l]["set"], reply_markup=kb) # Відправляємо нове повідомлення з Reply-клавіатурою
    await cb.answer(TEXTS[l]["set"])

@dp.message(F.text.func(lambda m: m in [TEXTS[x]["btn"] for x in TEXTS]))
async def combos(msg: types.Message):
    """Відправляє комбо-коди."""
    l = get_lang(msg.from_user.id)
    today_date = datetime.now().strftime('%d.%m.%Y')
    
    # Текст з комбо
    text = f"<b>Комбо та коди на {today_date}</b>\n\n"
    text += ("Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
              "Blum → Cipher: FREEDOM\n"
              "TapSwap → MATRIX\n"
              "CATS → MEOW2025\n"
              "Rocky Rabbit → 3→1→4→2\n"
              "Yescoin → ←↑→↓←\n"
              "DOGS → DOGS2025\n"
              "+ ще 15 ігор щодня…")

    # Перевірка статусу оплати
    paid = False
    if os.path.exists(PAID_FILE):
        try:
            with open(PAID_FILE, encoding="utf-8") as f:
                # Читаємо всі рядки і перевіряємо, чи є ID користувача
                paid_users = [line.strip() for line in f]
                if str(msg.from_user.id) in paid_users:
                    paid = True
        except IOError as e:
            logger.error(f"Помилка читання {PAID_FILE}: {e}")
            
    if not paid:
        # Клавіатура для неоплаченого користувача
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Преміум 1$", url="https://t.me/send?start=IVWQeJXKYVsd")],
            [types.InlineKeyboardButton(text="Я оплатив", callback_data="paid")]
        ])
        text += "\n\n<b>Преміум 1$</b> — ранній доступ + сигнали"
        await msg.answer(text, reply_markup=kb)
    else:
        # Клавіатура для оплаченого користувача
        await msg.answer(text)

@dp.callback_query(F.data == "paid")
async def paid_check(cb: types.CallbackQuery):
    """Обробник кнопки "Я оплатив". Активація преміуму."""
    
    user_id = str(cb.from_user.id)
    
    try:
        with open(PAID_FILE, "a", encoding="utf-8") as f:
            f.write(f"{user_id}\n")
    except IOError as e:
        logger.error(f"Неможливо записати до {PAID_FILE}: {e}")
        await cb.message.edit_text("Помилка активації преміуму. Спробуйте пізніше.")
        await cb.answer()
        return

    await cb.message.edit_text("Преміум активовано назавжди! ✅ Тепер ви маєте повний доступ.")
    await cb.answer()
    
@dp.message()
async def echo_handler(message: types.Message):
    """Обробник для будь-яких інших повідомлень, які не є командами чи кнопками."""
    l = get_lang(message.from_user.id)
    # Повертаємо користувача до початку (можливо, він писав щось незрозуміле)
    await message.answer(TEXTS[l]["start"], reply_markup=lang_kb)


async def main():
    logger.info("БОТ @CryptoComboDaily — 100% ЖИВИЙ")
    # Видаляємо пропущені оновлення при старті для чистого запуску
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот зупинено вручну.")
    except Exception as e:
        logger.error(f"Критична помилка запуску: {e}")
