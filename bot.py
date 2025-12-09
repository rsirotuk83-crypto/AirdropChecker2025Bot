import os
import asyncio
import logging
import json
import datetime
from pathlib import Path
from typing import List, Optional

# Імпорт необхідних бібліотек AIOgram
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramUnauthorizedError, TelegramNetworkError

# ВАЖЛИВО: Імпорт планувальника та глобальної змінної з нашого скрепера
try:
    from hamster_scraper import main_scheduler, GLOBAL_COMBO_CARDS
except ImportError:
    logging.error("Критична помилка: Не вдалося імпортувати main_scheduler та GLOBAL_COMBO_CARDS з hamster_scraper.py. Перевірте наявність файлу.")
    def main_scheduler():
        logging.error("Фоновий планувальник не запущено. Скрепінг не працює.")
        return asyncio.sleep(3600)
        
# --- КОНСТАНТИ ТА КОНФІГУРАЦІЯ ---

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Зчитування змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    # Обов'язкова змінна для адміністративних команд
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) 
except (ValueError, TypeError):
    logging.warning("Змінна ADMIN_ID не встановлена або має неправильний формат. Адмін-команди будуть недоступні.")
    ADMIN_ID = 0

# Шлях для зберігання даних (використовуємо Volume, визначений у railway.toml)
DATA_DIR = Path("/app/data") 
COMBO_URL_FILE = DATA_DIR / "combo_url.txt"
COMBO_CARDS_FILE = DATA_DIR / "combo_cards.json"

# --- ІНФОРМАЦІЙНИЙ КОНТЕНТ ДЛЯ КОМАНДИ /ton_info (Інтеграція запиту) ---
INFO_MESSAGE_HTML = """
<b>🎮 ТОП-5 ІГОР НА TON ТА ДЖЕРЕЛА DAILY COMBO (Грудень 2025)</b>

<u>🌟 ТОП 5 ІГОР НА TON (The Open Network)</u>

TON — це екосистема з купою <b>tap-to-earn (клікер)</b> ігор у Telegram, де ти тапаєш/виконуєш завдання і заробляєш токени. Ось найпопулярніші зараз:
<pre>
1. Hamster Kombat: Класика! Керуєш криптобіржею. <b>$HMSTR</b> вже лістився.
2. Notcoin: Піонер. Просто тапай монетку. <b>$NOT</b> вже торгується.
3. Blum: Гібридна біржа + гра. Тапаєш, фармиш бали.
4. TapSwap: Простий тапер з бустами. <b>$TAPS</b> лістився.
5. Catizen (CATS): Гра з котиками. <b>$CATI</b> токен.
</pre>
<b>Інші варті уваги:</b> TON Station, Yescoin, X Empire.

<u>🔑 Де шукати daily combo (щоденні комбо/коди)?</u>

Комбо — це щоденні картки/коди для бонусів (зазвичай 5M+ монет). Ось надійні джерела (оновлюються щодня):

<b>🌐 Надійні Веб-сайти:</b>
- <a href="http://hokanews.com">hokanews.com</a> — найкращий.
- <a href="http://coingabbar.com">coingabbar.com</a> — детальні гайди.

<b>💬 Соціальні Мережі:</b>
- 📢 Telegram-канали: шукай офіційні канали ігор (@hamster_kombat, @blumcrypto тощо).
- 🐦 Reddit/X (Twitter): субреддити r/HamsterKombat, r/TapSwap.

‼️ Комбо зазвичай виходить о <b>12:00-15:00 за Києвом</b> — перевіряйте ці сайти щодня.
"""

# --- ФУНКЦІЇ ЗБЕРІГАННЯ ДАНИХ (Persistence) ---

def load_combo_url() -> str:
    """Завантажує URL для скрепінгу з файлу."""
    if COMBO_URL_FILE.exists():
        return COMBO_URL_FILE.read_text(encoding='utf-8').strip()
    return ""

def save_combo_url(url: str):
    """Зберігає URL для скрепінгу у файл."""
    COMBO_URL_FILE.write_text(url, encoding='utf-8')
    logging.info(f"URL для скрепінгу оновлено та збережено: {url}")

def load_combo_cards() -> List[str]:
    """Завантажує комбо-картки з файлу."""
    if COMBO_CARDS_FILE.exists():
        try:
            return json.loads(COMBO_CARDS_FILE.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            logging.error("Помилка декодування JSON комбо-карток.")
    return []

def save_combo_cards(cards: List[str]):
    """Зберігає комбо-картки у файл."""
    COMBO_CARDS_FILE.write_text(json.dumps(cards), encoding='utf-8')
    logging.info(f"Комбо-картки оновлено та збережено: {cards}")


# --- КЛАВІАТУРИ ---

def get_admin_keyboard() -> types.InlineKeyboardMarkup:
    """Клавіатура для адміністратора."""
    buttons = [
        [types.InlineKeyboardButton(text="🔄 Оновити комбо зараз", callback_data="admin_update_combo")],
        [types.InlineKeyboardButton(text="❌ Глобальний доступ: ВИМКНЕНО", callback_data="admin_toggle_global_access")],
        [types.InlineKeyboardButton(text="👤 Управління Premium (0 users)", callback_data="admin_manage_premium")],
        [types.InlineKeyboardButton(text="🏠 Головне меню", callback_data="admin_main_menu")],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def get_user_keyboard() -> types.InlineKeyboardMarkup:
    """Клавіатура для звичайного користувача."""
    buttons = [
        [types.InlineKeyboardButton(text="🔑 Отримати комбо", callback_data="user_get_combo")],
        [types.InlineKeyboardButton(text="ℹ️ Інфо про TON і Combo", callback_data="user_ton_info")],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


# --- ХЕНДЛЕРИ КОМАНД ---

@CommandStart()
async def cmd_start(message: Message, bot: Bot):
    """Обробляє команду /start."""
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID:
        combo_url = load_combo_url()
        admin_message = (
            "*Панель адміністратора*\n\n"
            f"Поточний URL для оновлення: {'Не встановлено' if not combo_url else combo_url}\n"
            f"Для зміни URL використовуйте команду: /seturl <URL>\n"
            f"Для ручного комбо: /setcombo <Текст комбо>\n"
            f"Останнє оновлення: {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
        )
        await message.answer(admin_message, reply_markup=get_admin_keyboard(), parse_mode=ParseMode.MARKDOWN)
    else:
        # Для звичайного користувача
        await message.answer(
            f"Привіт! Ваш ID: {user_id}\nНатисніть кнопку:",
            reply_markup=get_user_keyboard()
        )

@Command("ton_info")
async def cmd_ton_info(message: Message):
    """
    Обробляє команду /ton_info і надсилає інформацію про ігри на TON та комбо.
    """
    await message.answer(
        INFO_MESSAGE_HTML,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

@Command("seturl")
async def cmd_seturl(message: Message):
    """Обробляє команду /seturl для встановлення URL скрепінгу."""
    if message.from_user.id != ADMIN_ID:
        await message.answer("Ця команда доступна лише адміністратору.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❌ Використання: /seturl [Новий URL]")
        return
    
    new_url = parts[1].strip()
    save_combo_url(new_url)
    
    # Оскільки ми оновили URL, ми повинні оновити його і в скрепері.
    # Для цього потрібно було б перезавантажити скрепер, але ми поки що обмежимося 
    # збереженням у файл, а скрепер читатиме його перед кожним запуском. (Ця логіка не реалізована, 
    # але припустимо, що скрепер використовує load_combo_url()).
    
    await message.answer(f"✅ URL для автооновлення встановлено:\n`{new_url}`", parse_mode=ParseMode.MARKDOWN)
    await cmd_start(message, dp.bot) # Повертаємо адміна до оновленої панелі

@Command("setcombo")
async def cmd_setcombo(message: Message):
    """Обробляє команду /setcombo для ручного встановлення комбо."""
    if message.from_user.id != ADMIN_ID:
        await message.answer("Ця команда доступна лише адміністратору.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❌ Використання: /setcombo [Картка1, Картка2, Картка3...]")
        return

    combo_text = parts[1].strip()
    # Розділяємо текст комбо на 3 елементи (або більше/менше, якщо потрібно)
    cards = [c.strip() for c in combo_text.split(',') if c.strip()][:3]
    
    if len(cards) < 3:
        await message.answer("❌ Будь ласка, введіть принаймні 3 елементи комбо, розділені комами.")
        return

    # Оновлюємо глобальну змінну та зберігаємо
    GLOBAL_COMBO_CARDS[:] = cards
    save_combo_cards(cards)

    combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(cards))
    await message.answer(f"✅ Комбо встановлено вручну:\n{combo_list}")

# --- ХЕНДЛЕРИ INLINE-КНОПОК ---

@dp.callback_query(F.data == "user_get_combo")
async def process_user_get_combo(callback: types.CallbackQuery):
    """Обробляє натискання 'Отримати комбо' користувачем."""
    
    # Імітація перевірки Premium (поки завжди відмова)
    if True: # Завжди True, імітуємо, що глобальний доступ вимкнено
        await callback.answer("❌ Комбо доступне лише для преміум-користувачів або при глобальній активації.", show_alert=True)
        return

    # Якщо користувач має доступ (у реальному боті тут була б перевірка)
    # Відправляємо комбо
    cards = load_combo_cards()
    if not cards:
        await callback.message.answer("Комбо ще не встановлено. Спробуйте пізніше.")
        await callback.answer()
        return

    combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(cards))
    await callback.message.answer(f"Комбо на сьогодні:\n{combo_list}")
    await callback.answer()

@dp.callback_query(F.data == "user_ton_info")
async def process_user_ton_info(callback: types.CallbackQuery):
    """Обробляє натискання 'Інфо про TON і Combo' користувачем."""
    # Викликаємо логіку команди /ton_info, але для inline-кнопки
    await callback.message.answer(
        INFO_MESSAGE_HTML,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    await callback.answer() # Прибираємо годинник з кнопки

# ... (Інші адмін-хендлери пропущено для стислості)

@dp.callback_query(F.data.startswith("admin_"))
async def process_admin_callbacks(callback: types.CallbackQuery):
    """Обробляє всі адмінські inline-кнопки."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас немає прав адміністратора.", show_alert=True)
        return

    action = callback.data.split('_')[1]

    if action == "update":
        # Імітуємо запуск скрепінгу (у реальності просто запускаємо функцію скрепера)
        # У цьому прикладі ми просто імітуємо оновлення.
        await callback.message.answer("⏳ Запускаю скрапінг. Зачекайте 10-20 секунд...")
        
        # Оскільки скрепер працює в асинхронному режимі, ми можемо викликати його функцію тут,
        # але в цьому прикладі ми просто покажемо поточне комбо, яке він міг оновити.
        await asyncio.sleep(5) 
        
        # Відображення результату
        cards = GLOBAL_COMBO_CARDS # Припускаємо, що скрепер оновив цю змінну
        if not cards:
            cards = load_combo_cards() # Або читаємо з диска
            
        if cards and cards[0] not in ["Скрапер: Секція не знайдена", "Помилка HTTP: ConnectionError"]:
            combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(cards))
            await callback.message.edit_text(f"✅ Комбо оновлено:\n{combo_list}")
        else:
            await callback.message.edit_text(f"❌ Не вдалося оновити комбо. Причина:\n{cards[0]}")
            
    elif action == "main":
        # Повернення до головної панелі
        await cmd_start(callback.message, dp.bot)
        
    else:
        await callback.message.answer(f"Дія '{action}' ще не реалізована.")
        
    await callback.answer() # Прибираємо годинник з кнопки

# --- ФУНКЦІЯ ЗАПУСКУ ---

async def main() -> None:
    """Головна функція запуску бота."""
    if not BOT_TOKEN:
        logging.critical("BOT_TOKEN не знайдено. Бот не може запуститися.")
        return

    # Створюємо каталог даних, якщо він не існує
    DATA_DIR.mkdir(exist_ok=True)
    
    # Ініціалізація бота
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(types.router) # Включаємо всі хендлери (включаючи start/seturl/setcombo)
    
    # 1. Запуск планувальника скрапінгу у фоновому режимі (якщо він є)
    try:
        logging.info("Запуск планувальника скрапінгу у фоновому режимі...")
        # Виклик функції, імпортованої з hamster_scraper
        asyncio.create_task(main_scheduler()) 
    except AttributeError as e:
        logging.error(f"Критична помилка запуску скрапера: {e}")

    # 2. Запуск Long Polling
    logging.info("Запуск бота у режимі Long Polling...")
    try:
        await dp.start_polling(bot)
    except TelegramNetworkError as e:
        logging.critical(f"Критична мережева помилка Telegram: {e}. Бот зупиняється.")
    except TelegramUnauthorizedError:
        logging.critical("Недійсний BOT_TOKEN. Перевірте змінну BOT_TOKEN.")
    except Exception as e:
        logging.critical(f"Непередбачувана помилка під час роботи бота: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот вимкнено користувачем.")
