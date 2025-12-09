import os
import asyncio
import logging
import json
import datetime
from pathlib import Path
from typing import List, Optional

# Імпорт необхідних бібліотек AIOgram
from aiogram import Bot, Dispatcher, types, F, Router # << ІМПОРТ ROUTER
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramUnauthorizedError, TelegramNetworkError

# ВАЖЛИВО: Імпорт планувальника та глобальної змінної з нашого скрепера
try:
    # Припускаємо, що hamster_scraper тепер налаштований на TON Station
    from hamster_scraper import main_scheduler, GLOBAL_COMBO_CARDS
except ImportError:
    logging.error("Критична помилка: Не вдалося імпортувати main_scheduler та GLOBAL_COMBO_CARDS з hamster_scraper.py. Перевірте наявність файлу.")
    async def main_scheduler():
        logging.error("Фоновий планувальник не запущено. Скрепінг не працює.")
        await asyncio.sleep(3600)
        
# --- ІНІЦІАЛІЗАЦІЯ ROUTER ---
router = Router()

# --- КОНСТАНТИ ТА КОНФІГУРАЦІЯ ---

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Зчитування змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) 
except (ValueError, TypeError):
    logging.warning("Змінна ADMIN_ID не встановлена або має неправильний формат.")
    ADMIN_ID = 0

# Шлях для зберігання даних
DATA_DIR = Path("/app/data") 
COMBO_URL_FILE = DATA_DIR / "combo_url.txt"
COMBO_CARDS_FILE = DATA_DIR / "combo_cards.json"

# --- ІНФОРМАЦІЙНИЙ КОНТЕНТ ДЛЯ КОМАНДИ /ton_info ---
INFO_MESSAGE_HTML = """
<b>🎮 TON STATION ТА DAILY COMBO</b>

<u>🚀 Гра: TON Station</u>
TON Station — це одна з найперспективніших ігор у Telegram-екосистемі TON. Вона фокусується на геймплеї "tap-to-earn" із функціями будівництва станції.
* <b>Токен:</b> $SOON
* <b>Особливість:</b> Щоденне комбо дає значний приріст токенів $SOON.

<u>🔑 Де шукати daily combo для TON Station?</u>

Комбо TON Station — це 4 картки, які дають <b>2000 $SOON</b> токенів.

<b>🌐 Надійне Джерело (Скрапиться ботом):</b>
- <a href="https://miningcombo.com/ton-station/">miningcombo.com/ton-station/</a>

<b>‼️ Важливо:</b> Комбо оновлюється щодня, зазвичай о <b>12:00-15:00 за Києвом</b>.
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
            # Читаємо з диска для відображення
            return json.loads(COMBO_CARDS_FILE.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            logging.error("Помилка декодування JSON комбо-карток.")
    # Якщо глобальна змінна була оновлена скрепером, використовуємо її
    return GLOBAL_COMBO_CARDS 

def save_combo_cards(cards: List[str]):
    """Зберігає комбо-картки у файл."""
    COMBO_CARDS_FILE.write_text(json.dumps(cards), encoding='utf-8')
    logging.info(f"Комбо-картки оновлено та збережено: {cards}")


# --- КЛАВІАТУРИ ---

def get_admin_keyboard() -> types.InlineKeyboardMarkup:
    """Клавіатура для адміністратора."""
    # Примітка: Клавіатура тут спрощена, але у реальному боті вона має бути оновлена 
    # відповідно до поточного статусу глобального доступу.
    buttons = [
        [types.InlineKeyboardButton(text="🔄 Оновити комбо зараз", callback_data="admin_update_combo")],
        [types.InlineKeyboardButton(text="❌ Глобальний доступ: ВИМКНЕНО", callback_data="admin_toggle_global_access")],
        [types.InlineKeyboardButton(text="🏠 Головне меню", callback_data="admin_main_menu")],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def get_user_keyboard() -> types.InlineKeyboardMarkup:
    """Клавіатура для звичайного користувача."""
    buttons = [
        [types.InlineKeyboardButton(text="🔑 Отримати комбо (TON Station)", callback_data="user_get_combo")],
        [types.InlineKeyboardButton(text="ℹ️ Інфо про TON Station", callback_data="user_ton_info")],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


# --- ХЕНДЛЕРИ КОМАНД (ПРИКРІПЛЕНІ ДО ROUTER) ---

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    """Обробляє команду /start."""
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID:
        # У цьому випадку bot.py читає TARGET_URL з самого себе, тому load_combo_url() не спрацює,
        # але ми залишаємо заглушку для універсальності.
        combo_url = "TON Station (miningcombo.com)" 
        admin_message = (
            "*Панель адміністратора*\n\n"
            f"Поточне джерело скрапінгу: {combo_url}\n"
            f"Для ручного комбо: /setcombo <Карта1, Карта2, Карта3, Карта4>\n"
            f"Останнє оновлення: {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
        )
        await message.answer(admin_message, reply_markup=get_admin_keyboard(), parse_mode=ParseMode.MARKDOWN)
    else:
        # Для звичайного користувача
        await message.answer(
            f"Привіт! Я бот для щоденного комбо TON Station. Ваш ID: {user_id}\nВиберіть опцію:",
            reply_markup=get_user_keyboard()
        )

@router.message(Command("ton_info"))
async def cmd_ton_info(message: Message):
    """
    Обробляє команду /ton_info і надсилає інформацію про TON Station.
    """
    await message.answer(
        INFO_MESSAGE_HTML,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

@router.message(Command("seturl"))
async def cmd_seturl(message: Message):
    """Ця команда тепер є заглушкою, оскільки URL жорстко заданий у scraper.py."""
    if message.from_user.id != ADMIN_ID:
        await message.answer("Ця команда доступна лише адміністратору.")
        return
    await message.answer("❌ URL скрапінгу жорстко заданий у файлі `hamster_scraper.py` і не може бути змінений цією командою. Поточна ціль: TON Station.")

@router.message(Command("setcombo"))
async def cmd_setcombo(message: Message):
    """Обробляє команду /setcombo для ручного встановлення комбо."""
    if message.from_user.id != ADMIN_ID:
        await message.answer("Ця команда доступна лише адміністратору.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❌ Використання: /setcombo [Картка1, Картка2, Картка3, Картка4...]")
        return

    combo_text = parts[1].strip()
    # Розділяємо текст комбо на 4 елементи (для TON Station)
    cards = [c.strip() for c in combo_text.split(',') if c.strip()][:4]
    
    if len(cards) < 4:
        await message.answer("❌ Будь ласка, введіть рівно 4 елементи комбо для TON Station, розділені комами.")
        return

    # Оновлюємо глобальну змінну та зберігаємо
    GLOBAL_COMBO_CARDS[:] = cards
    save_combo_cards(cards)

    combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(cards))
    await message.answer(f"✅ Комбо TON Station встановлено вручну:\n{combo_list}")


# --- ХЕНДЛЕРИ INLINE-КНОПОК ---

# Хендлери кнопок повинні бути прикріплені до роутера або диспетчера
@router.callback_query(F.data == "user_get_combo")
async def process_user_get_combo(callback: types.CallbackQuery):
    """Обробляє натискання 'Отримати комбо' користувачем."""
    
    # Імітація перевірки Premium (поки завжди відмова)
    if True: # Завжди True, імітуємо, що глобальний доступ вимкнено
        await callback.answer("❌ Комбо доступне лише для преміум-користувачів або при глобальній активації.", show_alert=True)
        return

    # Якщо користувач має доступ (у реальному боті тут була б перевірка)
    cards = load_combo_cards() # Читаємо з глобальної змінної або файлу

    if not cards or cards[0].startswith("Скрапер:"):
        await callback.message.answer("Комбо ще не встановлено або сталася помилка скрапінгу. Спробуйте пізніше або зверніться до адміна.")
        await callback.answer()
        return

    combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(cards))
    await callback.message.answer(f"🔥 *Комбо TON Station на сьогодні* (4 карти):\n{combo_list}", parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@router.callback_query(F.data == "user_ton_info")
async def process_user_ton_info(callback: types.CallbackQuery):
    """Обробляє натискання 'Інфо про TON і Combo' користувачем."""
    await callback.message.answer(
        INFO_MESSAGE_HTML,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_"))
async def process_admin_callbacks(callback: types.CallbackQuery):
    """Обробляє всі адмінські inline-кнопки."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас немає прав адміністратора.", show_alert=True)
        return

    action = callback.data.split('_')[1]
    
    if action == "update":
        from hamster_scraper import scrape_for_combo # Імпортуємо функцію скрапінгу
        await callback.message.edit_text("⏳ Запускаю ручний скрапінг TON Station. Зачекайте...")
        
        # Скрапінг відбувається синхронно, але ми запускаємо його в окремому потоці
        # (aiogram.run_in_threadpool або, для простоти, просто чекаємо)
        new_combo = await asyncio.to_thread(scrape_for_combo) 
        
        if new_combo and new_combo[0] not in ["Скрапер: Секція не знайдена", "Помилка HTTP: ConnectionError"]:
            GLOBAL_COMBO_CARDS[:] = new_combo
            save_combo_cards(new_combo)
            combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(new_combo))
            await callback.message.edit_text(f"✅ Комбо оновлено:\n{combo_list}", reply_markup=get_admin_keyboard())
        else:
            await callback.message.edit_text(f"❌ Не вдалося оновити комбо. Причина:\n{new_combo}", reply_markup=get_admin_keyboard())
            
    elif action == "main":
        # Повернення до головної панелі
        await cmd_start(callback.message, callback.bot) # Викликаємо хендлер start
        
    else:
        await callback.message.answer(f"Дія '{action}' ще не реалізована.")
        
    await callback.answer()

# --- ФУНКЦІЯ ЗАПУСКУ ---

async def main() -> None:
    """Головна функція запуску бота."""
    if not BOT_TOKEN:
        logging.critical("BOT_TOKEN не знайдено. Бот не може запуститися.")
        return

    DATA_DIR.mkdir(exist_ok=True)
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # КРИТИЧНО: Включаємо роутер з усіма хендлерами в диспетчер
    dp.include_router(router) 
    
    # 1. Запуск планувальника скрапінгу у фоновому режимі
    try:
        logging.info("Запуск планувальника скрапінгу у фоновому режимі...")
        asyncio.create_task(main_scheduler()) 
    except AttributeError as e:
        logging.error(f"Критична помилка запуску скрапера: {e}")

    # 2. Запуск Long Polling
    logging.info("Запуск бота у режимі Long Polling...")
    try:
        # Важливо: використовуємо bot замість dp.bot
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
