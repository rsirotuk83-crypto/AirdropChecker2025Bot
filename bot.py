import os
import asyncio
import logging
import json
import datetime
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Імпорт для Webhooks та асинхронного веб-сервера
from aiohttp import web 

# Імпорт необхідних бібліотек AIOgram
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.methods import DeleteWebhook, SetWebhook

# ВАЖЛИВО: Імпорт планувальника та глобальної змінної з нашого скрепера
try:
    from hamster_scraper import main_scheduler, GLOBAL_COMBO_CARDS
except ImportError:
    logging.error("Критична помилка: Не вдалося імпортувати scraper. Фоновий планувальник не запуститься.")
    async def main_scheduler():
        logging.error("Фоновий планувальник не запущено. Скрепінг не працює.")
        await asyncio.sleep(3600)

# --- КОНСТАНТИ ТА КОНФІГУРАЦІЯ ---

load_dotenv()
# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Зчитування змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) 
except (ValueError, TypeError):
    logger.warning("Змінна ADMIN_ID не встановлена або має неправильний формат.")
    ADMIN_ID = 0

# --- КОНФІГУРАЦІЯ WEBHOOKS (КРИТИЧНО ДЛЯ RAILWAY) ---
# WEBHOOK_HOST повинен бути доменом, наданим Railway (e.g., airdropchecker2025bot-production.up.railway.app)
# WEBHOOK_PATH - шлях, на який Telegram надсилатиме оновлення
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") # Читається як домен
WEBHOOK_PATH = "/webhook"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080)) # Порт, який надає Railway

if WEBHOOK_HOST:
    # URL, який ми передамо Telegram
    WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"
else:
    logger.critical("WEBHOOK_HOST не знайдено. Бот не зможе працювати через Webhooks.")
    WEBHOOK_URL = None


# Шлях для зберігання даних
DATA_DIR = Path("/app/data") 
COMBO_CARDS_FILE = DATA_DIR / "combo_cards.json"

# ІНФОРМАЦІЙНИЙ КОНТЕНТ
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

# --- ІНІЦІАЛІЗАЦІЯ ROUTER ТА ДИСПЕТЧЕРА ---
router = Router()
dp = Dispatcher()
dp.include_router(router) 

# --- ФУНКЦІЇ ЗБЕРІГАННЯ ДАНИХ (Persistence) ---

def load_combo_cards() -> List[str]:
    """Завантажує комбо-картки з файлу."""
    if COMBO_CARDS_FILE.exists():
        try:
            return json.loads(COMBO_CARDS_FILE.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            logger.error("Помилка декодування JSON комбо-карток.")
    return GLOBAL_COMBO_CARDS 

def save_combo_cards(cards: List[str]):
    """Зберігає комбо-картки у файл."""
    COMBO_CARDS_FILE.write_text(json.dumps(cards), encoding='utf-8')
    logger.info(f"Комбо-картки оновлено та збережено: {cards}")


# --- КЛАВІАТУРИ ---

def get_admin_keyboard() -> types.InlineKeyboardMarkup:
    """Клавіатура для адміністратора."""
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


# --- ХЕНДЛЕРИ КОМАНД ---

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    """Обробляє команду /start."""
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID:
        combo_url = "TON Station (miningcombo.com)" 
        admin_message = (
            "*Панель адміністратора*\n\n"
            f"Поточне джерело скрапінгу: {combo_url}\n"
            f"Для ручного комбо: /setcombo <Карта1, Карта2, Карта3, Карта4>\n"
            f"Останнє оновлення: {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
        )
        await message.answer(admin_message, reply_markup=get_admin_keyboard(), parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer(
            f"Привіт! Я бот для щоденного комбо TON Station. Ваш ID: {user_id}\nВиберіть опцію:",
            reply_markup=get_user_keyboard()
        )

@router.message(Command("ton_info"))
async def cmd_ton_info(message: Message):
    """Обробляє команду /ton_info."""
    await message.answer(
        INFO_MESSAGE_HTML,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

@router.message(Command("seturl"))
async def cmd_seturl(message: Message):
    """Заглушка для seturl."""
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
    cards = [c.strip() for c in combo_text.split(',') if c.strip()][:4]
    
    if len(cards) < 4:
        await message.answer("❌ Будь ласка, введіть рівно 4 елементи комбо для TON Station, розділені комами.")
        return

    GLOBAL_COMBO_CARDS[:] = cards
    save_combo_cards(cards)

    combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(cards))
    await message.answer(f"✅ Комбо TON Station встановлено вручну:\n{combo_list}")


# --- ХЕНДЛЕРИ INLINE-КНОПОК ---

@router.callback_query(F.data == "user_get_combo")
async def process_user_get_combo(callback: types.CallbackQuery):
    """Обробляє натискання 'Отримати комбо' користувачем."""
    
    # Зараз ця логіка імітує відмову (тому що немає реальної перевірки Premium)
    # Щоб дати користувачеві комбо, замініть True на False.
    if True: 
        await callback.answer("❌ Комбо доступне лише для преміум-користувачів або при глобальній активації.", show_alert=True)
        return

    cards = load_combo_cards() 

    if not cards or cards[0].startswith("Скрапер:"):
        await callback.message.answer("Комбо ще не встановлено або сталася помилка скрапінгу. Спробуйте пізніше.")
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
        from hamster_scraper import scrape_for_combo
        await callback.message.edit_text("⏳ Запускаю ручний скрапінг TON Station. Зачекайте...")
        
        # Виконуємо скрепінг в окремому потоці, щоб не блокувати Event Loop
        new_combo = await asyncio.to_thread(scrape_for_combo) 
        
        if new_combo and not new_combo[0].startswith("Скрапер:") and not new_combo[0].startswith("Помилка HTTP:"):
            GLOBAL_COMBO_CARDS[:] = new_combo
            save_combo_cards(new_combo)
            combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(new_combo))
            await callback.message.edit_text(f"✅ Комбо оновлено:\n{combo_list}", reply_markup=get_admin_keyboard())
        else:
            await callback.message.edit_text(f"❌ Не вдалося оновити комбо. Причина:\n{new_combo[0]}", reply_markup=get_admin_keyboard())
            
    elif action == "main":
        # Повернення до головної панелі
        await cmd_start(callback.message, callback.bot)
        
    else:
        await callback.message.answer(f"Дія '{action}' ще не реалізована.")
        
    await callback.answer()


# --- ФУНКЦІЇ WEBHOOK ---

async def on_startup(bot: Bot) -> None:
    """Викликається при запуску. Встановлює Webhook."""
    if WEBHOOK_URL:
        # Видаляємо попередній Webhook (для очищення від Long Polling)
        await bot(DeleteWebhook(drop_pending_updates=True))
        # Встановлюємо новий Webhook
        logger.info(f"Встановлюю Webhook на URL: {WEBHOOK_URL}")
        await bot(SetWebhook(url=WEBHOOK_URL, allowed_updates=dp.resolve_used_update_types()))
    else:
        logger.error("Не вдалося встановити Webhook, оскільки WEBHOOK_URL не визначено.")

async def on_shutdown(bot: Bot) -> None:
    """Викликається при зупинці. Видаляє Webhook."""
    logger.info("Видаляю Webhook...")
    await bot(DeleteWebhook(drop_pending_updates=True))
    logger.info("Webhook видалено. Бот зупинено.")

async def start_background_tasks(app: web.Application) -> None:
    """Запускає фонові завдання (планувальник скрепінгу) при старті сервера."""
    app['combo_scheduler'] = asyncio.create_task(main_scheduler())
    logger.info("Фоновий планувальник скрепінгу запущено.")

async def cleanup_background_tasks(app: web.Application) -> None:
    """Очищає фонові завдання при зупинці сервера."""
    app['combo_scheduler'].cancel()
    await app['combo_scheduler']
    logger.info("Фоновий планувальник скрепінгу зупинено.")

async def init_webhook_server(bot: Bot) -> web.Application:
    """Ініціалізує aiohttp Webhook сервер."""
    if not WEBHOOK_HOST:
        raise ValueError("WEBHOOK_HOST не знайдено.")

    # Реєстрація хендлерів запуску/зупинки (якщо потрібно)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    app = web.Application()
    
    # aiohttp хендлер, який передає запити Telegram в aiogram
    webhook_requests_handler = dp.get_web_app(bot=bot, path=WEBHOOK_PATH)
    app.router.add_route("POST", WEBHOOK_PATH, webhook_requests_handler)
    
    # Реєстрація завдань, що запускаються при старті та зупинці Webhook-сервера
    app.on_startup.append(lambda a: on_startup(bot))
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    app.on_cleanup.append(lambda a: on_shutdown(bot))

    return app

def main() -> None:
    """Головна функція запуску бота."""
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN не знайдено. Бот не може запуститися.")
        return
    if not WEBHOOK_HOST:
        logger.critical("WEBHOOK_HOST не знайдено. Бот не може запуститися через Webhooks.")
        return

    DATA_DIR.mkdir(exist_ok=True)
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    # Ініціалізація та запуск Webhook-сервера
    try:
        logger.info(f"Запуск Webhook-сервера на http://0.0.0.0:{WEB_SERVER_PORT}{WEBHOOK_PATH}")
        app = init_webhook_server(bot)
        
        # web.run_app блокує виконання, що дозволяє Railway підтримувати контейнер активним
        web.run_app(app, host='0.0.0.0', port=WEB_SERVER_PORT) 
    
    except TelegramUnauthorizedError:
        logger.critical("Недійсний BOT_TOKEN. Перевірте змінну BOT_TOKEN.")
    except Exception as e:
        logger.critical(f"Непередбачувана критична помилка під час роботи бота: {e}")

if __name__ == "__main__":
    main()
