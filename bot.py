import os
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import List
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiogram.client.default import DefaultBotProperties
from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.storage.memory import MemoryStorage
from aiohttp import web
import re

# --- УТИЛІТИ ---
def escape_markdown_v2(text: str) -> str:
    """Екранує спеціальні символи MarkdownV2 у тексті."""
    # Символи, які потрібно екранувати, якщо вони не використовуються для форматування
    escape_chars = r'_*[]()~`>#+-=|{}.!\\'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# --- КРИТИЧНО ВАЖЛИВИЙ БЛОК ІМПОРТУ СКРАПЕРА ---
# ІМПОРТУЄМО ЛОГІКУ СКРАПЕРА
try:
    # Припускаємо, що ці об'єкти існують у hamster_scraper.py
    from hamster_scraper import main_scheduler, GLOBAL_COMBO_CARDS, _scrape_for_combo 
    SCAPER_AVAILABLE = True
except ImportError as e:
    logging.error(f"Не вдалося імпортувати компоненти скрапера з hamster_scraper.py: {e}. Скрапер не працюватиме.")
    
    # Заглушка, якщо скрапер не знайдено
    async def main_scheduler():
        logging.warning("Фоновий планувальник не запущений. Скрапінг не працює.")
        await asyncio.sleep(3600)
    async def _scrape_for_combo():
        logging.warning("Функція _scrape_for_combo недоступна.")
        return ["ImportError: Scraper not found"]
        
    GLOBAL_COMBO_CARDS = []
    SCAPER_AVAILABLE = False

# --- НАЛАШТУВАННЯ БАЗИ ДАНИХ (DB) ---
class BotDB:
# ... (весь клас BotDB залишається незмінним) ...
    def __init__(self, data_dir="data", db_file="db.json"):
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, db_file)
        os.makedirs(data_dir, exist_ok=True)
        logging.info(f"Перевірено або створено директорію даних: {self.data_dir}")
        self.data = self._load_data()
        
    def _load_data(self):
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logging.info(f"Дані успішно завантажено з {self.db_path}")
        except FileNotFoundError:
            logging.warning(f"Файл бази даних {self.db_path} не знайдено. Будуть використані початкові значення.")
            data = {
                "users": {},
                "global_combo": [],
                "global_access": False,
                "admin_id": int(os.environ.get("ADMIN_ID", 0)),
                "admin_is_premium": False,
                "payment_token": os.environ.get("CRYPTO_BOT_TOKEN"),
                "webhook_url": None,
                "auto_update_url": None,
            }
            self._save_data(data)
        except json.JSONDecodeError:
            logging.error(f"Помилка декодування JSON у файлі {self.db_path}. Використовуються початкові значення.")
            data = {
                "users": {},
                "global_combo": [],
                "global_access": False,
                "admin_id": int(os.environ.get("ADMIN_ID", 0)),
                "admin_is_premium": False,
                "payment_token": os.environ.get("CRYPTO_BOT_TOKEN"),
                "webhook_url": None,
                "auto_update_url": None,
            }
        
        # Додаткова перевірка/ініціалізація полів, якщо їх немає
        if 'global_combo' not in data:
             data['global_combo'] = []
        if 'global_access' not in data:
             data['global_access'] = False

        return data

    def _save_data(self, data):
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logging.info(f"Дані успішно збережено у {self.db_path}")
        except Exception as e:
            logging.error(f"Помилка збереження даних: {e}")

    def get_user(self, user_id):
        return self.data["users"].get(str(user_id), {})

    def set_user_premium(self, user_id, is_premium=True):
        user_id_str = str(user_id)
        if user_id_str not in self.data["users"]:
            self.data["users"][user_id_str] = {"is_premium": is_premium, "premium_until": None}
        else:
            self.data["users"][user_id_str]["is_premium"] = is_premium
        self._save_data(self.data)

    def is_premium(self, user_id):
        # Якщо це адмін, і він був помічений як преміум при старті (через логіку нижче), то він преміум
        if user_id == self.data.get("admin_id") and self.data.get("admin_is_premium"):
            return True

        user = self.get_user(user_id)
        return user.get("is_premium", False)

    def set_global_combo(self, combo: List[str]):
        self.data["global_combo"] = combo
        self._save_data(self.data)

    def get_global_combo(self):
        return self.data["global_combo"]

    def set_global_access(self, status: bool):
        self.data["global_access"] = status
        self._save_data(self.data)

    def get_global_access(self):
        return self.data["global_access"]

    def get_admin_id(self):
        return self.data.get("admin_id")
    
    def set_auto_update_url(self, url):
        self.data["auto_update_url"] = url
        self._save_data(self.data)

    def get_auto_update_url(self):
        return self.data.get("auto_update_url")

db = BotDB()
admin_id_from_env = int(os.environ.get("ADMIN_ID", 0))

# Перевірка та встановлення адміна як преміум, якщо його ID було надано
if admin_id_from_env and admin_id_from_env == db.get_admin_id():
    db.set_user_premium(admin_id_from_env, is_premium=True)
    db.data["admin_is_premium"] = True
    logging.info(f"Адмін ID {admin_id_from_env} додано до Premium.")

# --- КОНСТАНТИ WEBHOOKS ---
WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST")
WEBHOOK_PATH = f"/webhook/{os.environ.get('BOT_TOKEN')}"
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.environ.get("PORT", 8080))

if not WEBHOOK_HOST:
    logging.warning("WEBHOOK_HOST не встановлено. Бот працюватиме в режимі Polling (для локального запуску).")
    IS_WEBHOOK = False
else:
    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    IS_WEBHOOK = True
    
# --- STATES ---
class AdminState(StatesGroup):
    SET_COMBO = State()
    SET_URL = State()

# --- HANDLERS ---
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="Отримати комбо 🔑", callback_data="get_combo")],
    ]
    if db.get_admin_id() and db.get_admin_id() != 0:
         keyboard.append([InlineKeyboardButton(text="Адмінка ⚙️", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_keyboard(access_status: bool, combo_set: bool):
    keyboard = [
        [InlineKeyboardButton(text="Оновити комбо зараз 🔄", callback_data="force_fetch_combo")],
        [InlineKeyboardButton(text=f"Глобальний доступ: {'✅ УВІМКНЕНО' if access_status else '❌ ВИМКНЕНО'}", callback_data="toggle_global_access")],
        [InlineKeyboardButton(text="Встановити комбо вручну 📝", callback_data="set_combo_manual")],
        [InlineKeyboardButton(text="Встановити URL для автооновлення 🔗", callback_data="set_auto_url")],
        [InlineKeyboardButton(text="Управління Premium (0 users) 💎", callback_data="manage_premium")],
        [InlineKeyboardButton(text="Головне меню 🏠", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    user_id = message.from_user.id
    is_admin = user_id == db.get_admin_id()
    
    greeting = f"Привіт! Ваш ID: {user_id}" if is_admin else "Привіт!"
    
    await message.answer(
        f"{greeting} \nНатисніть кнопку:",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.HTML
    )

async def admin_panel(c: types.CallbackQuery | types.Message, state: FSMContext) -> None:
    # Оскільки c може бути або CallbackQuery, або Message, ми обробляємо це
    if isinstance(c, types.CallbackQuery):
        await c.answer()
        message_to_edit = c.message
        user_id = c.from_user.id
    elif isinstance(c, types.Message):
        message_to_edit = c
        user_id = c.from_user.id
    else:
        logging.error("Неправильний тип аргументу, очікується CallbackQuery або Message")
        return
    
    await state.clear()
    
    if user_id != db.get_admin_id():
        # Якщо це Message, ми не можемо викликати c.answer. Просто повертаємось.
        if isinstance(c, types.CallbackQuery):
            await c.answer("У вас немає доступу до панелі адміністратора.", show_alert=True)
        return
        
    global_access = db.get_global_access()
    combo = db.get_global_combo()
    combo_text = ", ".join(combo) if combo else "Не встановлено"
    
    auto_url = db.get_auto_update_url()
    
    text = (
        "*Панель адміністратора*\n\n"
        f"**Комбо (Scraper):** `{escape_markdown_v2(combo_text)}`\n" # Екрануємо комбо_текст
        f"Поточний URL для автооновлення: {escape_markdown_v2(auto_url) if auto_url else 'Не встановлено'}\n\n"
    )
    
    try:
        await message_to_edit.edit_text(
            text,
            reply_markup=get_admin_keyboard(global_access, bool(combo)),
            parse_mode=ParseMode.MARKDOWN_V2 # Залишаємо MARKDOWN_V2 для консистентності
        )
    except TelegramBadRequest as e:
        # ЦЕЙ БЛОК ЛОВИТЬ ПОМИЛКУ "message is not modified", ЯКА БУЛА У ВАШИХ ЛОГАХ.
        if "message is not modified" in str(e):
            logging.info("Admin panel message content is identical, skipping edit.")
        else:
            # Інша помилка при редагуванні, про всяк випадок
            logging.error(f"Помилка редагування адмін-панелі: {e}")

@dp.callback_query(lambda c: c.data == "admin_panel")
async def process_admin_panel(c: types.CallbackQuery, state: FSMContext):
    await admin_panel(c, state)

@dp.callback_query(lambda c: c.data == "main_menu")
async def process_main_menu(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    # Замість виклику command_start_handler, використовуємо edit_text для оновлення поточного повідомлення
    await c.message.edit_text(
        f"Привіт! Ваш ID: {c.from_user.id} \nНатисніть кнопку:",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.HTML # HTML використовуємо тут, щоб уникнути складного екранування в початковому повідомленні
    )
    await c.answer()

@dp.callback_query(lambda c: c.data == "toggle_global_access")
async def toggle_global_access(c: types.CallbackQuery, state: FSMContext):
    user_id = c.from_user.id
    if user_id != db.get_admin_id():
        await c.answer("У вас немає доступу.", show_alert=True)
        return

    new_status = not db.get_global_access()
    db.set_global_access(new_status)
    await c.answer(f"Глобальний доступ: {'УВІМКНЕНО' if new_status else 'ВИМКНЕНО'}", show_alert=True)
    # Повернення на оновлену панель
    await admin_panel(c, state) 

@dp.callback_query(lambda c: c.data == "set_combo_manual")
async def set_combo_manual(c: types.CallbackQuery, state: FSMContext):
    if c.from_user.id != db.get_admin_id():
        await c.answer("У вас немає доступу.", show_alert=True)
        return
    
    await c.message.edit_text("Введіть 3 картки комбо, розділені комою (наприклад: Card1, Card2, Card3):",
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                  [InlineKeyboardButton(text="Скасувати", callback_data="admin_panel")]
                              ]))
    await state.set_state(AdminState.SET_COMBO)
    await c.answer()

@dp.message(AdminState.SET_COMBO)
async def process_set_combo(message: types.Message, state: FSMContext):
    if message.from_user.id != db.get_admin_id(): return # Захист
        
    combo_input = message.text.split(',')
    combo_list = [c.strip() for c in combo_input if c.strip()]
    
    if len(combo_list) != 3:
        await message.answer("Помилка: Ви повинні ввести рівно 3 картки, розділені комою. Спробуйте ще раз:",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="Скасувати", callback_data="admin_panel")]
                             ]))
        return

    db.set_global_combo(combo_list)
    if 'GLOBAL_COMBO_CARDS' in globals():
        GLOBAL_COMBO_CARDS[:] = combo_list # Оновлюємо глобальну змінну скрапера, якщо вона була імпортована
    
    # Використовуємо escape_markdown_v2 для виводу повідомлення
    escaped_combo = escape_markdown_v2(", ".join(combo_list))
    await message.answer(f"✅ Комбо оновлено: {escaped_combo}", parse_mode=ParseMode.MARKDOWN_V2)
    
    await state.clear()
    # Перехід на панель адміна
    await admin_panel(message, state) # Використовуємо Message

@dp.callback_query(lambda c: c.data == "set_auto_url")
async def set_auto_url(c: types.CallbackQuery, state: FSMContext):
    if c.from_user.id != db.get_admin_id():
        await c.answer("У вас немає доступу.", show_alert=True)
        return
    
    await c.message.edit_text("Введіть URL, звідки бот повинен автоматично отримувати комбо (або `Н/Д` для вимкнення):",
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                  [InlineKeyboardButton(text="Скасувати", callback_data="admin_panel")]
                              ]))
    await state.set_state(AdminState.SET_URL)
    await c.answer()

@dp.message(AdminState.SET_URL)
async def process_set_url(message: types.Message, state: FSMContext):
    if message.from_user.id != db.get_admin_id(): return # Захист
        
    url = message.text.strip()
    
    if url.lower() == "н/д" or url.lower() == "нд":
        db.set_auto_update_url(None)
        await message.answer("✅ Автооновлення комбо вимкнено.")
    elif not (url.startswith('http://') or url.startswith('https://')):
        await message.answer("Помилка: URL має починатися з `http://` або `https://`. Спробуйте ще раз:",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="Скасувати", callback_data="admin_panel")]
                             ]))
        return
    else:
        db.set_auto_update_url(url)
        # Використовуємо escape_markdown_v2 для виводу URL
        escaped_url = escape_markdown_v2(url)
        await message.answer(f"✅ URL для автооновлення встановлено: {escaped_url}", parse_mode=ParseMode.MARKDOWN_V2)
    
    await state.clear()
    # Перехід на панель адміна
    await admin_panel(message, state)

@dp.message(Command("seturl"))
async def set_auto_url_command(message: types.Message, state: FSMContext):
    # Перевірка на адміна
    if message.from_user.id != db.get_admin_id():
        await message.answer("У вас немає доступу до цієї команди.")
        return

    # Перевірка наявності аргументу
    args = message.text.split(' ', 1)
    if len(args) < 2:
        await message.answer("❌ Використання: /seturl <URL-адреса>\n\nПриклад: /seturl https://example.com/combo_data")
        return

    url = args[1].strip()

    if url.lower() in ["н/д", "нд", "none"]:
        db.set_auto_update_url(None)
        await message.answer("✅ Автооновлення комбо вимкнено.")
    elif not (url.startswith('http://') or url.startswith('https://')):
        await message.answer("Помилка: URL має починатися з `http://` або `https://`.")
        return
    else:
        db.set_auto_update_url(url)
        # Використовуємо escape_markdown_v2 для виводу URL
        escaped_url = escape_markdown_v2(url)
        await message.answer(f"✅ URL для автооновлення встановлено: {escaped_url}", parse_mode=ParseMode.MARKDOWN_V2)
        
    # Очищаємо стан
    await state.clear()

@dp.callback_query(lambda c: c.data == "force_fetch_combo")
async def force_fetch_combo(c: types.CallbackQuery, state: FSMContext):
    if c.from_user.id != db.get_admin_id():
        await c.answer("У вас немає доступу.", show_alert=True)
        return
    
    await c.answer("Запускаю скрапінг комбо...", show_alert=False)
    
    if not SCAPER_AVAILABLE:
        await c.message.answer("❌ Скрапер недоступний \\(ImportError\\)\\. Перевірте файл `hamster_scraper.py`\\.", parse_mode=ParseMode.MARKDOWN_V2)
        logging.error("Спроба виконати скрапінг при недоступному SCAPER_AVAILABLE.")
    else:
        try:
            # Виконуємо скрапінг синхронно в окремому потоці
            new_combo = await asyncio.to_thread(_scrape_for_combo) 

            if new_combo and new_combo[0] not in ["Помилка: Секція не знайдена", "Помилка: Неповне комбо", "ImportError: Scraper not found"]:
                db.set_global_combo(new_combo)
                if 'GLOBAL_COMBO_CARDS' in globals():
                    GLOBAL_COMBO_CARDS[:] = new_combo
                escaped_combo = escape_markdown_v2(", ".join(new_combo))
                await c.message.answer(f"✅ Комбо оновлено скрапером: {escaped_combo}", parse_mode=ParseMode.MARKDOWN_V2)
                logging.info(f"Скрапінг успішно оновив комбо: {new_combo}")
            else:
                error_msg = escape_markdown_v2(new_combo[0] if new_combo else "Невідома помилка скрапінгу.")
                await c.message.answer(f"❌ Скрапінг не зміг отримати нове комбо\\. Результат: {error_msg}", parse_mode=ParseMode.MARKDOWN_V2)
                logging.warning(f"Скрапінг повернув помилку: {error_msg}")
                
        except Exception as e:
            escaped_error = escape_markdown_v2(f"{type(e).__name__}: {e}")
            await c.message.answer(f"❌ Критична помилка під час виконання скрапінгу: {escaped_error}", parse_mode=ParseMode.MARKDOWN_V2)
            logging.error(f"Критична помилка під час виконання _scrape_for_combo: {e}", exc_info=True)
         
    # Повернення на оновлену панель
    await admin_panel(c, state)

@dp.callback_query(lambda c: c.data == "get_combo")
async def process_get_combo(c: types.CallbackQuery):
    user_id = c.from_user.id
    is_premium = db.is_premium(user_id)
    global_access = db.get_global_access()
    combo = db.get_global_combo()
    
    # Відповідаємо на колбек, щоб уникнути TelegramBadRequest,
    # і тільки після цього надсилаємо повідомлення
    await c.answer() 
    
    if global_access or is_premium:
        if combo:
            # --- ВИПРАВЛЕННЯ: ЗАСТОСУВАННЯ ЕКРАНУВАННЯ MDV2 ДЛЯ УСЬОГО ТЕКСТУ ---
            
            # Екрануємо дату
            today_date = escape_markdown_v2(datetime.now().strftime("%d.%m.%Y"))
            
            # Екрануємо кожен елемент комбо, потім обгортаємо в жирний шрифт (\*...\*)
            combo_text_list = []
            for i, card in enumerate(combo):
                # Спочатку екрануємо вміст картки
                escaped_card_name = escape_markdown_v2(card)
                # Потім додаємо форматування (порядковий номер, крапку і жирний шрифт)
                combo_text_list.append(f"{i+1}\. \*{escaped_card_name}\*")
            
            combo_text = "\n".join(combo_text_list)
            
            response = (
                f"\*Комбо на {today_date}\*\n\n"
                "Щоденний набір карток для отримання 5,000,000 монет:\n\n"
                f"{combo_text}\n\n"
                "\_P\.S\.: Не забувайте про Daily Cipher\!\_"
            )
            await c.message.answer(response, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await c.message.answer("Комбо ще не встановлено\\. Адміністратор, встановіть його вручну або налаштуйте URL\\.", parse_mode=ParseMode.MARKDOWN_V2)
            
    else:
        # Надсилаємо повідомлення про обмеження
        await c.message.answer("❌ Комбо доступне лише для преміум\\-користувачів або при глобальній активації\\.", parse_mode=ParseMode.MARKDOWN_V2)
        
# --- WEBHOOKS & APP SETUP ---
async def on_startup(bot: Bot) -> None:
    if IS_WEBHOOK:
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
        logging.info(f"Webhook встановлено на: {WEBHOOK_URL}")
    
    # Запуск планувальника скрапінгу у фоновому режимі
    logging.info("Запуск планувальника скрапінгу у фоновому режимі...")
    asyncio.create_task(main_scheduler())

async def on_shutdown(bot: Bot) -> None:
    if IS_WEBHOOK:
        await bot.delete_webhook()
        logging.info("Webhook видалено.")

async def handle_webhook(request: web.Request):
    bot = request.app['bot']
    dispatcher = request.app['dp']

    if request.match_info.get('token') != os.environ.get('BOT_TOKEN'):
        return web.Response(status=403)

    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dispatcher.feed_update(bot, update)
    return web.Response()

def main_polling() -> None:
    # Запуск в режимі Polling (для локального запуску)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    logging.info("БОТ УСПІШНО ЗАПУЩЕНО — ПОЧИНАЄМО ПОЛЛІНГ")
    try:
        # У режимі Polling Webhook-функції не запускаються
        asyncio.run(dp.start_polling(bot))
    except KeyboardInterrupt:
        logging.info("Бот вимкнено.")

def main_webhook() -> None:
    # Запуск в режимі Webhook
    
    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    
    # Реєстрація хендлера вебхука
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    
    # Реєстрація on_startup/on_shutdown
    app.on_startup.append(lambda a: on_startup(bot))
    app.on_shutdown.append(lambda a: on_shutdown(bot))
    
    logging.info(f"БОТ УСПІШНО ЗАПУЩЕНО — ПОЧИНАЄМО WEBHOOK на порту {WEB_SERVER_PORT}")
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)


if __name__ == "__main__":
    # Налаштування логування
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Ініціалізація бота
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        logging.error("КРИТИЧНА ПОМИЛКА: BOT_TOKEN не встановлено.")
    
    # Ініціалізуємо бот з ParseMode.MARKDOWN_V2 за замовчуванням
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
    dp = Dispatcher(storage=MemoryStorage())
    
    # Реєстрація хендлерів
    dp.message.register(command_start_handler, CommandStart())
    dp.callback_query.register(process_admin_panel, lambda c: c.data == "admin_panel")
    dp.callback_query.register(process_main_menu, lambda c: c.data == "main_menu")
    dp.callback_query.register(toggle_global_access, lambda c: c.data == "toggle_global_access")
    dp.callback_query.register(set_combo_manual, lambda c: c.data == "set_combo_manual")
    dp.callback_query.register(set_auto_url, lambda c: c.data == "set_auto_url")
    dp.message.register(process_set_combo, AdminState.SET_COMBO)
    dp.message.register(process_set_url, AdminState.SET_URL)
    dp.callback_query.register(force_fetch_combo, lambda c: c.data == "force_fetch_combo")
    dp.callback_query.register(process_get_combo, lambda c: c.data == "get_combo")
    dp.message.register(set_auto_url_command, Command("seturl")) 

    if IS_WEBHOOK:
        main_webhook()
    else:
        main_polling()
