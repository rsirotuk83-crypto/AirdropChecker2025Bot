import os
import asyncio
import logging
import json
import datetime
from pathlib import Path
from typing import List, Dict, Union, Any
from dotenv import load_dotenv

from aiohttp import web 
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.methods import DeleteWebhook, SetWebhook

# ВАЖЛИВО: Імпорт планувальника та глобальної змінної з нашого скрепера
try:
    # Імпорт необхідних елементів з hamster_scraper.py
    from hamster_scraper import main_scheduler, GLOBAL_COMBO_CARDS, COMBO_SOURCES, scrape_for_combo
except ImportError:
    # Обробка помилки, якщо файл scraper не знайдено або в ньому помилка
    logger.error("Критична помилка: Не вдалося імпортувати scraper. Фоновий планувальник не запуститься.")
    async def main_scheduler():
        logger.error("Фоновий планувальник не запущено. Скрепінг не працює.")
        await asyncio.sleep(3600)
    # Використовуємо заглушки, щоб бот міг запуститися
    COMBO_SOURCES = {
        "TON Station": "https://miningcombo.com/ton-station/",
        "Hamster Kombat": "https://hamster-combo.com/",
        "TapSwap": "https://miningcombo.com/tapswap-2/",
        "Blum": "https://miningcombo.com/blum-2/",
        "Cattea": "https://miningcombo.com/cattea/",
    }
    GLOBAL_COMBO_CARDS = {game: [f"Скрапер: Недоступно (помилка імпорту scraper)"] for game in COMBO_SOURCES}
    def scrape_for_combo(game: str, url: str) -> List[str]: return [f"Помилка: Scraper не імпортовано для {game}."]

# --- КОНСТАНТИ ТА КОНФІГУРАЦІЯ ---

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Змінні середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) 
except (ValueError, TypeError):
    logger.warning("Змінна ADMIN_ID не встановлена або має неправильний формат.")
    ADMIN_ID = 0

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") 
WEBHOOK_PATH = "/webhook"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080)) 

# Формування WEBHOOK_URL
if WEBHOOK_HOST:
    WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"
else:
    logger.critical("WEBHOOK_HOST не знайдено. Бот не зможе працювати через Webhooks.")
    WEBHOOK_URL = None

# Налаштування директорії для постійного зберігання даних (persistence)
DATA_DIR = Path("/app/data") 
COMBO_CARDS_FILE = DATA_DIR / "all_combo_cards.json"

# --- ІНФОРМАЦІЙНИЙ КОНТЕНТ (Універсальна функція) ---
def get_info_message(game: str, url: str) -> str:
    """Генерує інформаційне повідомлення для конкретної гри."""
    base_info = f"""
<b>🎮 {game} ТА DAILY COMBO</b>

<u>🚀 Гра: {game}</u>
{game} — це популярна гра в Telegram-екосистемі.

<u>🔑 Де шукати daily combo для {game}?</u>

Комбо {game} — це 3 або 4 картки, які дають значний приріст токенів.

<b>🌐 Надійне Джерело:</b>
- <a href="{url}">{url.replace('https://', '').replace('http://', '')}</a>

<b>‼️ Важливо:</b> Комбо оновлюється щодня, час залежить від гри.
"""
    # Додаємо специфічну інфу, якщо вона є
    if game == "TON Station":
         return base_info + "<b>Специфіка:</b> Комбо оновлюється зазвичай о <b>12:00-15:00 за Києвом</b>."
    if game == "Hamster Kombat":
         return base_info + "<b>Специфіка:</b> Комбо оновлюється щодня о <b>15:00 за Києвом</b>."
    return base_info


# --- ІНІЦІАЛІЗАЦІЯ ROUTER ТА ДИСПЕТЧЕРА ---
router = Router()
dp = Dispatcher()
dp.include_router(router) 

# --- ФУНКЦІЇ ЗБЕРІГАННЯ ДАНИХ (Persistence) ---

def load_combo_cards() -> Dict[str, Union[List[str], List[str]]]:
    """Завантажує всі комбо-картки з файлу. Використовує GLOBAL_COMBO_CARDS як fallback/default."""
    if COMBO_CARDS_FILE.exists():
        try:
            loaded_data = json.loads(COMBO_CARDS_FILE.read_text(encoding='utf-8'))
            
            # Перевіряємо, чи всі ігри з COMBO_SOURCES присутні в завантажених даних
            for game in COMBO_SOURCES:
                if game not in loaded_data:
                     # Додаємо відсутні ігри із заглушками
                     loaded_data[game] = [f"Скрапер: Комбо для {game} не знайдено у файлі."]
            
            return loaded_data
        except json.JSONDecodeError:
            logger.error("Помилка декодування JSON комбо-карток. Повертаю дані з пам'яті.")
    
    # Повертаємо дані з пам'яті (які ініціалізовані або скрапером, або заглушками)
    return GLOBAL_COMBO_CARDS 

def save_combo_cards(cards: Dict[str, Union[List[str], List[str]]]):
    """Зберігає всі комбо-картки у файл."""
    try:
        COMBO_CARDS_FILE.write_text(json.dumps(cards, ensure_ascii=False, indent=4), encoding='utf-8')
        logger.info(f"Всі комбо-картки оновлено та збережено.")
    except Exception as e:
        logger.error(f"Помилка при збереженні комбо-карток у файл: {e}")


# --- КЛАВІАТУРИ ---

def get_admin_keyboard(game_name: str) -> types.InlineKeyboardMarkup:
    """Клавіатура для адміністратора, прив'язана до конкретної гри."""
    buttons = [
        [types.InlineKeyboardButton(text=f"🔄 Оновити {game_name} зараз", callback_data=f"admin_update_{game_name}")],
        [types.InlineKeyboardButton(text="❌ Глобальний доступ: ВИМКНЕНО", callback_data="admin_toggle_global_access")], # Заглушка
        [types.InlineKeyboardButton(text="🏠 Головне меню", callback_data="admin_main_menu")],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def get_game_selection_keyboard(action_prefix: str) -> types.InlineKeyboardMarkup:
    """Клавіатура вибору гри для отримання комбо або інфо."""
    buttons = []
    
    # Створюємо кнопки для кожної гри
    for game in COMBO_SOURCES.keys():
        # Колбек: user_get_combo:TON Station
        buttons.append(types.InlineKeyboardButton(text=f"🔑 {game}", callback_data=f"{action_prefix}:{game}"))
    
    # Додаємо кнопку Інформація (яка також відкриє селектор)
    buttons.append(types.InlineKeyboardButton(text="ℹ️ Інформація про ігри", callback_data="show_info_selector"))

    # Розбиваємо на рядки по 2 кнопки
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


# --- ХЕНДЛЕРИ КОМАНД ---

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    """Обробляє команду /start."""
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID:
        # Для адміна показуємо статус
        current_data = load_combo_cards()
        combo_status = "\n".join([
            f"  - {game}: {'✅ OK' if not current_data.get(game, [''])[0].startswith('Скрапер:') else '❌ ERR'}" 
            for game in COMBO_SOURCES.keys()
        ])
        
        admin_message = (
            "*Панель адміністратора*\n\n"
            f"Поточний статус скрапінгу:\n{combo_status}\n\n"
            f"Для ручного комбо: /setcombo <Гра> <Карта1, ...>\n"
            f"Останнє оновлення: {datetime.datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
        )
        
        await message.answer(
            admin_message, 
            reply_markup=get_game_selection_keyboard("admin_check_combo"), 
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Для звичайного користувача
        await message.answer(
            f"Привіт! Я бот для щоденних комбо {len(COMBO_SOURCES)} популярних Web3 ігор. Ваш ID: {user_id}\n\n"
            "Виберіть гру, щоб отримати її сьогоднішнє комбо:",
            reply_markup=get_game_selection_keyboard("user_get_combo")
        )

@router.message(Command("setcombo"))
async def cmd_setcombo(message: Message):
    """Обробляє команду /setcombo для ручного встановлення комбо для конкретної гри."""
    if message.from_user.id != ADMIN_ID:
        await message.answer("Ця команда доступна лише адміністратору.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            f"❌ Використання: /setcombo [Назва Гри] [Картка1, Картка2, Картка3, Картка4...]\n"
            f"Наприклад: /setcombo TapSwap Карта A, Карта B, Карта C\n"
            f"Доступні ігри: {', '.join(COMBO_SOURCES.keys())}"
        )
        return

    game_name = parts[1].strip()
    combo_text = parts[2].strip()

    if game_name not in COMBO_SOURCES:
        await message.answer(f"❌ Невідома гра: {game_name}. Доступні: {', '.join(COMBO_SOURCES.keys())}")
        return

    cards = [c.strip() for c in combo_text.split(',') if c.strip()][:4]
    
    if len(cards) < 3:
        await message.answer(f"❌ Будь ласка, введіть принаймні 3 елементи комбо для {game_name}, розділені комами.")
        return

    # Оновлюємо глобальну змінну та зберігаємо на диск
    GLOBAL_COMBO_CARDS[game_name] = cards
    save_combo_cards(GLOBAL_COMBO_CARDS)

    combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(cards))
    await message.answer(f"✅ Комбо для *{game_name}* встановлено вручну:\n{combo_list}", parse_mode=ParseMode.MARKDOWN)


# --- ХЕНДЛЕРИ INLINE-КНОПОК (User & Admin) ---

# Селектор для Інформації
@router.callback_query(F.data == "show_info_selector")
async def process_show_info_selector(callback: types.CallbackQuery):
    """Показує клавіатуру для вибору гри, про яку користувач хоче отримати інфо."""
    await callback.message.edit_text(
        "ℹ️ Виберіть гру, щоб дізнатися деталі про її щоденне комбо:",
        reply_markup=get_game_selection_keyboard("user_info") # Використовуємо префікс 'user_info'
    )
    await callback.answer()


# Обробка запиту комбо користувачем (user_get_combo:Game Name)
@router.callback_query(F.data.startswith("user_get_combo:"))
async def process_user_get_combo(callback: types.CallbackQuery):
    """Обробляє натискання 'Отримати комбо' користувачем для конкретної гри."""
    
    game_name = callback.data.split(':', 1)[1]
    
    # Завантажуємо актуальні дані (навіть якщо вони з помилкою)
    cards = load_combo_cards().get(game_name)

    if not cards or cards[0].startswith("Скрапер:") or cards[0].startswith("Помилка HTTP:"):
        await callback.message.answer(
            f"❌ Комбо для *{game_name}* ще не встановлено або сталася помилка скрапінгу. Спробуйте пізніше.\n\n"
            f"Остання помилка: _{cards[0] if cards else 'Немає даних'}_",
            parse_mode=ParseMode.MARKDOWN
        )
        await callback.answer()
        return

    combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(cards))
    
    # Додаємо кнопку 'Інфо' в повідомлення з комбо
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"ℹ️ Про {game_name}", callback_data=f"user_info:{game_name}")],
        [types.InlineKeyboardButton(text="🏠 Головне меню", callback_data="admin_main_menu")], # Перевикористовуємо колбек для повернення до початку
    ])
    
    await callback.message.answer(
        f"🔥 *Комбо {game_name} на сьогодні* ({len(cards)} карт):\n{combo_list}", 
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )
    await callback.answer()


# Обробка запиту інфо користувачем (user_info:Game Name)
@router.callback_query(F.data.startswith("user_info:"))
async def process_user_info(callback: types.CallbackQuery):
    """Обробляє натискання 'Інфо' користувачем для конкретної гри."""
    game_name = callback.data.split(':', 1)[1]
    url = COMBO_SOURCES.get(game_name, "Невідомий URL")
    
    await callback.message.edit_text(
        get_info_message(game_name, url),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        # Додаємо кнопку "Отримати Комбо" і "Назад"
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=f"🔑 Отримати Комбо {game_name}", callback_data=f"user_get_combo:{game_name}")],
            [types.InlineKeyboardButton(text="🏠 Головне меню", callback_data="admin_main_menu")],
        ])
    )
    await callback.answer()

# Обробка запиту перевірки комбо адміністратором (admin_check_combo:Game Name)
@router.callback_query(F.data.startswith("admin_check_combo:"))
async def process_admin_check_combo(callback: types.CallbackQuery):
    """Адмін: показує комбо та клавіатуру управління для обраної гри."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас немає прав адміністратора.", show_alert=True)
        return
        
    game_name = callback.data.split(':', 1)[1]
    cards = load_combo_cards().get(game_name)
    
    if not cards:
        status_text = "❌ Дані не знайдені."
    elif cards[0].startswith("Скрапер:") or cards[0].startswith("Помилка HTTP:"):
        status_text = f"❌ Помилка скрапінгу: {cards[0]}"
    else:
        combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(cards))
        status_text = f"✅ Поточне комбо *{game_name}* ({len(cards)} карт):\n{combo_list}"
        
    await callback.message.edit_text(
        f"*Панель адміністратора: {game_name}*\n\n{status_text}", 
        reply_markup=get_admin_keyboard(game_name),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()


# Обробка ручного оновлення (admin_update_Game Name)
@router.callback_query(F.data.startswith("admin_update_"))
async def process_admin_update(callback: types.CallbackQuery):
    """Обробляє ручне оновлення комбо адміністратором."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас немає прав адміністратора.", show_alert=True)
        return

    # admin_update_TON Station -> game_name = TON Station
    game_name = callback.data.split('admin_update_', 1)[1]
    
    if game_name not in COMBO_SOURCES:
        await callback.answer("❌ Невідома гра для оновлення.")
        return

    await callback.message.edit_text(f"⏳ Запускаю ручний скрапінг *{game_name}*. Зачекайте...", parse_mode=ParseMode.MARKDOWN)
    
    # Виконуємо скрепінг в окремому потоці
    new_combo = await asyncio.to_thread(scrape_for_combo, game_name, COMBO_SOURCES[game_name]) 
    
    if new_combo and not new_combo[0].startswith("Скрапер:") and not new_combo[0].startswith("Помилка HTTP:"):
        # Успіх: оновлюємо дані та зберігаємо
        GLOBAL_COMBO_CARDS[game_name] = new_combo
        save_combo_cards(GLOBAL_COMBO_CARDS)
        combo_list = "\n".join(f"{i+1}️⃣: {card}" for i, card in enumerate(new_combo))
        await callback.message.edit_text(
            f"✅ Комбо *{game_name}* оновлено:\n{combo_list}", 
            reply_markup=get_admin_keyboard(game_name),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # Помилка: показуємо повідомлення про помилку
        await callback.message.edit_text(
            f"❌ Не вдалося оновити комбо для *{game_name}*. Причина:\n{new_combo[0]}", 
            reply_markup=get_admin_keyboard(game_name),
            parse_mode=ParseMode.MARKDOWN
        )
        
    await callback.answer()

@router.callback_query(F.data == "admin_main_menu")
async def process_admin_main_menu(callback: types.CallbackQuery, bot: Bot):
    """Повертає користувача (або адміна) до головного меню."""
    await cmd_start(callback.message, bot)
    await callback.answer()
    
# Обробка заглушки "admin_toggle_global_access"
@router.callback_query(F.data == "admin_toggle_global_access")
async def process_admin_toggle_global_access(callback: types.CallbackQuery):
    await callback.answer("Функція 'Глобальний доступ' ще не реалізована.", show_alert=True)


# --- ФУНКЦІЇ WEBHOOK ---

async def on_startup_webhook(bot: Bot) -> None:
    """Викликається при запуску. Встановлює Webhook."""
    if WEBHOOK_URL:
        await bot(DeleteWebhook(drop_pending_updates=True))
        logger.info(f"Встановлюю Webhook на URL: {WEBHOOK_URL}")
        await bot(SetWebhook(url=WEBHOOK_URL, allowed_updates=dp.resolve_used_update_types()))
    else:
        logger.error("Не вдалося встановити Webhook, оскільки WEBHOOK_URL не визначено.")

async def on_shutdown_webhook(bot: Bot) -> None:
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
    if 'combo_scheduler' in app:
        app['combo_scheduler'].cancel()
        try:
            await app['combo_scheduler']
        except asyncio.CancelledError:
            pass 
        logger.info("Фоновий планувальник скрепінгу зупинено.")

async def init_webhook_server(bot: Bot) -> web.Application:
    """Асинхронно ініціалізує aiohttp Webhook сервер."""
    if not WEBHOOK_HOST:
        raise ValueError("WEBHOOK_HOST не знайдено.")

    dp.startup.register(on_startup_webhook)
    dp.shutdown.register(on_shutdown_webhook)
    
    app = web.Application()
    
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    ).register(app, path=WEBHOOK_PATH)
    
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    return app

def main() -> None:
    """Головна функція запуску бота."""
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN не знайдено. Бот не може запуститися.")
        return
    if not WEBHOOK_HOST:
        logger.critical("WEBHOOK_HOST не знайдено. Бот не може запуститися через Webhooks.")
        return

    # Створюємо директорію для даних, якщо вона не існує
    DATA_DIR.mkdir(exist_ok=True)
    
    # Завантажуємо дані при старті для ініціалізації GLOBAL_COMBO_CARDS
    global GLOBAL_COMBO_CARDS
    GLOBAL_COMBO_CARDS = load_combo_cards()
    
    # Ініціалізація бота
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    try:
        logger.info(f"Запуск Webhook-сервера на http://0.0.0.0:{WEB_SERVER_PORT}{WEBHOOK_PATH}")
        
        loop = asyncio.get_event_loop()
        app = loop.run_until_complete(init_webhook_server(bot))
        
        web.run_app(app, host='0.0.0.0', port=WEB_SERVER_PORT) 
    
    except TelegramUnauthorizedError:
        logger.critical("Недійсний BOT_TOKEN. Перевірте змінну BOT_TOKEN.")
    except Exception as e:
        logger.critical(f"Непередбачувана критична помилка під час роботи бота: {e}")

if __name__ == "__main__":
    main()
