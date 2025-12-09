import asyncio
import logging
import os
import signal
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.fsm.storage.memory import MemoryStorage

# --- Налаштування логування (Українська мова) ---
# Налаштовуємо основне логування
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Конфігурація середовища ---
# Отримання змінних середовища
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "airdropchecker2025bot-production.up.railway.app") # Використовуємо домен Railway як HOST за замовчуванням
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "very-secret-key") # Секретний токен для перевірки запитів
PORT = int(os.getenv("PORT", 8080))
WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"

# --- Ініціалізація Scraper (заглушка) ---
# Імітуємо модуль скрепінгу, який ви бачили в логах
class Scraper:
    def __init__(self):
        self.combo_cards = {}
        self.scheduler = None
        logger.info("Фоновий планувальник скрепінгу запущено.")

    async def load_combo_cards(self):
        # Заглушка для імітації завантаження даних
        await asyncio.sleep(0.5)
        self.combo_cards = {
            'Hamster Kombat': "Some combo data 1",
            'TON Station': "Some combo data 2"
        }
        logger.info("Завантаження комбо-карток завершено.")

    def start_scraping_scheduler(self):
        # Реальна логіка планувальника тут
        pass

# Створюємо глобальний екземпляр скрепера, щоб він був доступний у хендлерах
scraper = Scraper()

# --- Хендлери ---
main_router = Router()

@main_router.message()
async def all_messages(message):
    """Обробляє всі повідомлення, включаючи /start, якщо вони не оброблені іншими фільтрами."""
    # Перевіряємо, чи це команда /start
    if message.text == '/start':
        welcome_message = (
            "🎉 *Ласкаво просимо до AirdropChecker2025Bot!* 🎉\n\n"
            "Я тут, щоб допомогти вам не пропустити жодного щоденного комбо "
            "для ваших улюблених тапалок:\n"
            "▫️ Hamster Kombat\n"
            "▫️ TON Station\n"
            "▫️ TapSwap\n"
            "▫️ Blum\n"
            "▫️ Cattea\n\n"
            "Просто відправте мені назву гри або команду, щоб отримати актуальне комбо!\n\n"
            "*Доступні комбо:* " + ", ".join(scraper.combo_cards.keys())
        )
        await message.answer(welcome_message, parse_mode=ParseMode.MARKDOWN)
        return # Важливо завершити виконання

    # Обробка інших повідомлень
    game_name = message.text.strip()
    if game_name in scraper.combo_cards:
        await message.answer(f"Комбо для *{game_name}*: \n\n`{scraper.combo_cards[game_name]}`", parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer("Вибачте, я не знаю такої команди або гри. Спробуйте '/start'.")

# --- Webhook Hooks ---

async def on_startup_webhook(bot: Bot) -> None:
    """Виконується при запуску сервера: встановлює Webhook URL у Telegram."""
    logger.info(f"Встановлення Webhook URL: {WEBHOOK_URL}")
    await bot.set_webhook(url=WEBHOOK_URL, secret_token=WEBHOOK_SECRET)
    logger.info("Webhook успішно встановлено.")

async def on_shutdown_webhook(bot: Bot) -> None:
    """Виконується при зупинці сервера: видаляє Webhook URL з Telegram."""
    logger.info("Видалення Webhook URL.")
    await bot.delete_webhook()

# --- Основна функція запуску (Тепер асинхронна) ---

async def main() -> None:
    """Централізована асинхронна функція для ініціалізації та запуску Webhook-сервера."""
    
    if not BOT_TOKEN:
        logger.error("КРИТИЧНА ПОМИЛКА: Не знайдено змінну середовища BOT_TOKEN.")
        return

    # 1. Створення єдиних екземплярів Bot та Dispatcher
    # Використовуємо MemoryStorage, оскільки це простий бот
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    
    # 2. Реєстрація роутера
    dp.include_router(main_router)
    
    # 3. Реєстрація хуків (тепер dp вже існує)
    dp.startup.register(on_startup_webhook)
    dp.shutdown.register(on_shutdown_webhook)
    
    # 4. Попереднє завантаження даних скрепером
    logger.info("Запуск первинного завантаження даних...")
    await scraper.load_combo_cards()
    logger.info("Первинне завантаження завершено.")
    
    # 5. Налаштування Webhook-сервера aiohttp
    app = web.Application()

    # Створюємо хендлер, який підключає Bot та Dispatcher
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET
    )
    
    # Реєструємо хендлер для нашого WEBHOOK_PATH
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Налаштовуємо aiohttp app для Dispatcher (щоб він міг викликати startup/shutdown хуки)
    setup_application(app, dp, bot=bot)
    
    # 6. Запуск сервера
    logger.info(f"Запуск Webhook-сервера на http://0.0.0.0:{PORT}{WEBHOOK_PATH}")
    
    # Запуск фонового планувальника скрепінгу (якщо він є)
    scraper.start_scraping_scheduler()
    
    # Конфігурація для web.run_app
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=PORT)
    await site.start()
    
    # Тримаємо основний цикл в роботі до отримання сигналу зупинки
    stop_event = asyncio.Event()
    
    # Обробка сигналів для коректного завершення роботи
    def signal_handler(sig, frame):
        stop_event.set()
    
    # Реєстрація обробників сигналів
    if os.name == 'posix':
        asyncio.get_event_loop().add_signal_handler(signal.SIGINT, stop_event.set)
        asyncio.get_event_loop().add_signal_handler(signal.SIGTERM, stop_event.set)

    await stop_event.wait()
    
    # Коректне завершення роботи
    logger.info("Отримано сигнал зупинки. Завершення роботи...")
    await site.stop()
    await runner.cleanup()
    logger.info("Сервер зупинено.")

if __name__ == "__main__":
    try:
        # Тепер ми викликаємо асинхронну функцію main()
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот зупинено.")
    except Exception as e:
        logger.exception(f"Непередбачувана помилка під час виконання: {e}")
