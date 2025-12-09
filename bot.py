# ton_combo_bot_v2.py
"""
Оновлена версія бота TON Combo — v2
Покращення, внесені у цій версії:
- Заміна JSON-файлу на SQLite DB (ACID, безпечні записи, масштабування)
- Видалення глобальних змінних як джерел правди. Все зберігається в БД.
- Блокування операцій запису через asyncio.Lock для уникнення race conditions
- Покращений onboarding / тексти (free preview + чітка цінність)
- Чітка обробка admin_id (env або налаштування DB)
- Безпечне використання скрапера через try/except та оновлення DB
- Чітка структура: listeners / parser / publisher в одному файлі MVP
- Коментарі та TODO для подальшої прокачки

Примітка: цей файл призначений для MVP. Для production рекомендується
- відокремити модулі
- додати логування в файли
- додати monitoring / healthchecks
"""

import os
import re
import json
import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest
from aiogram.storage.memory import MemoryStorage

from aiohttp import web

# ---------------------------------------
# Конфіг
# ---------------------------------------
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID_ENV = os.environ.get("ADMIN_ID")
WEBHOOK_HOST = os.environ.get("WEBHOOK_HOST")
WEB_SERVER_PORT = int(os.environ.get("PORT", 8080))
WEB_SERVER_HOST = "0.0.0.0"
IS_WEBHOOK = bool(WEBHOOK_HOST)
if IS_WEBHOOK:
    WEBHOOK_PATH = f"/webhook/{TOKEN}"
    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

DB_PATH = os.environ.get("DB_PATH", "data/bot_v2.db")

# ---------------------------------------
# Легкий fallback для скрапера (імпортуємо якщо є)
# ---------------------------------------
try:
    from hamster_scraper import main_scheduler as scraper_main_scheduler, _scrape_for_combo
    SCRAPER_AVAILABLE = True
except Exception as e:
    logging.warning(f"Scraper not available: {e}")
    SCRAPER_AVAILABLE = False

    async def scraper_main_scheduler():
        while True:
            logging.info("Scraper placeholder sleeping (no scraper).")
            await asyncio.sleep(3600)

    async def _scrape_for_combo():
        return []

# ---------------------------------------
# Помічники
# ---------------------------------------
_escape_re = re.compile(r"([\\`*_\[\]()~>#\+\-=|{}.!])")

def escape_markdown_v2(text: str) -> str:
    if not text:
        return ""
    return _escape_re.sub(r"\\\\\\1", text)

# ---------------------------------------
# SQLite DB - невелика обгортка
# ---------------------------------------
class SQLiteDB:
    def __init__(self, path: str = DB_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self._init_db()
        self._lock = asyncio.Lock()

    def _get_conn(self):
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        cur = conn.cursor()
        # users: id, is_premium (0/1), premium_until ISO
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                is_premium INTEGER DEFAULT 0,
                premium_until TEXT
            )
        ''')
        # settings: key -> value (text)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # combos: id INTEGER PK ASC, text TEXT, created_at TEXT
        cur.execute('''
            CREATE TABLE IF NOT EXISTS combos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT,
                created_at TEXT
            )
        ''')
        conn.commit()
        conn.close()

    # SETTINGS helpers
    async def set_setting(self, key: str, value: Optional[str]):
        async with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            if value is None:
                cur.execute('DELETE FROM settings WHERE key = ?', (key,))
            else:
                cur.execute('REPLACE INTO settings(key, value) VALUES (?, ?)', (key, value))
            conn.commit()
            conn.close()

    async def get_setting(self, key: str) -> Optional[str]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cur.fetchone()
        conn.close()
        return row['value'] if row else None

    # USERS helpers
    async def set_user_premium(self, user_id: int, is_premium: bool = True, premium_until: Optional[str] = None):
        user_id_s = str(user_id)
        async with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('REPLACE INTO users(user_id, is_premium, premium_until) VALUES (?, ?, ?)',
                        (user_id_s, 1 if is_premium else 0, premium_until))
            conn.commit()
            conn.close()

    async def is_user_premium(self, user_id: int) -> bool:
        user_id_s = str(user_id)
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute('SELECT is_premium, premium_until FROM users WHERE user_id = ?', (user_id_s,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return False
        if row['is_premium'] == 1:
            # якщо є premium_until, перевіряємо дату
            if row['premium_until']:
                try:
                    until = datetime.fromisoformat(row['premium_until'])
                    return until >= datetime.utcnow()
                except Exception:
                    return True
            return True
        return False

    # COMBOS helpers
    async def add_combo(self, combo_text: str):
        async with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('INSERT INTO combos(text, created_at) VALUES (?, ?)', (combo_text, datetime.utcnow().isoformat()))
            conn.commit()
            conn.close()

    async def set_latest_combo(self, combo_text: str):
        # Для простоти: додамо як новий запис. Latest == останній рядок.
        await self.add_combo(combo_text)

    async def get_latest_combo(self) -> Optional[str]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute('SELECT text, created_at FROM combos ORDER BY id DESC LIMIT 1')
        row = cur.fetchone()
        conn.close()
        return row['text'] if row else None

    async def get_prev_combo(self) -> Optional[str]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute('SELECT text, created_at FROM combos ORDER BY id DESC LIMIT 2')
        rows = cur.fetchall()
        conn.close()
        if len(rows) >= 2:
            return rows[1]['text']
        return None

    async def get_admin_id(self) -> Optional[int]:
        val = await self.get_setting('admin_id')
        if val:
            try:
                return int(val)
            except Exception:
                return None
        return None

    async def set_admin_id(self, admin_id: int):
        await self.set_setting('admin_id', str(admin_id))

    async def set_auto_update_url(self, url: Optional[str]):
        await self.set_setting('auto_update_url', url)

    async def get_auto_update_url(self) -> Optional[str]:
        return await self.get_setting('auto_update_url')

# Ініціалізація DB
_db = SQLiteDB()

# Якщо ADMIN_ID у середовищі — встановлюємо у DB як опцію
if ADMIN_ID_ENV:
    try:
        asyncio.get_event_loop().run_until_complete(_db.set_admin_id(int(ADMIN_ID_ENV)))
        logging.info("Admin ID встановлено з ENV у DB")
    except Exception as e:
        logging.warning(f"Не вдалося встановити ADMIN_ID у DB: {e}")

# ---------------------------------------
# FSM States
# ---------------------------------------
class AdminState(StatesGroup):
    SET_COMBO = State()
    SET_URL = State()

# ---------------------------------------
# Bot і Dispatcher
# ---------------------------------------
if not TOKEN:
    raise SystemExit("BOT_TOKEN not set in environment")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher(storage=MemoryStorage())

# ---------------------------------------
# Кнопки та тексти (онбординг + UI)
# ---------------------------------------
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="Отримати комбо 🔑", callback_data="get_combo")],
        [InlineKeyboardButton(text="Про сервіс ℹ️", callback_data="about_service")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def get_admin_keyboard():
    admin_id = await _db.get_admin_id()
    access_status = True if await _db.get_setting('global_access') == '1' else False
    combo_exists = True if await _db.get_latest_combo() else False
    keyboard = [
        [InlineKeyboardButton(text="Оновити комбо зараз 🔄", callback_data="force_fetch_combo")],
        [InlineKeyboardButton(text=f"Глобальний доступ: {'✅ УВІМКНЕНО' if access_status else '❌ ВИМКНЕНО'}", callback_data="toggle_global_access")],
        [InlineKeyboardButton(text="Встановити комбо вручну 📝", callback_data="set_combo_manual")],
        [InlineKeyboardButton(text="Встановити URL для автооновлення 🔗", callback_data="set_auto_url")],
        [InlineKeyboardButton(text="Головне меню 🏠", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ---------------------------------------
# Handlers
# ---------------------------------------
@dp.message(CommandStart())
async def command_start_handler(message: types.Message, state: FSMContext):
    # onboarding
    admin_id = await _db.get_admin_id()
    is_admin = (message.from_user.id == admin_id) if admin_id else False

    text = (
        "🎮 *TON Game Combo Bot*\n\n"
        "✅ Всі щоденні комбо з TON-ігор в одному місці — щоб не шукати по чатах.\n"
        "⏱ Економить 5-15 хв кожного дня.\n\n"
        "*Що ти отримаєш безкоштовно:*\n"
        "– Назву гри та 1 картку з сьогоднішнього сету (швидкий прев’ю).\n\n"
        "*Преміум ($3/міс)* — всі карти, push-сповіщення, архів і доступ до всіх ігор.\n\n"
        "Натисни кнопку нижче, щоб отримати сьогоднішнє комбо або подивитися сервіс."
    )

    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode=ParseMode.MARKDOWN_V2)

@dp.callback_query(lambda c: c.data == "about_service")
async def about_service(c: types.CallbackQuery):
    text = (
        "*Як це працює*:\n"
        "1) Ми збираємо публічні комбо з офіційних каналів і Discord.\n"
        "2) Перевіряємо патерн та уникаємо дублікатів.\n"
        "3) Публікуємо в приватний канал / надсилаємо повідомлення преміум-користувачам.\n\n"
        "*Безпека:* Ми не ламаємо ігри і не використовуємо приватні ключі — лише публічну інформацію."
    )
    await c.message.answer(text, parse_mode=ParseMode.MARKDOWN_V2)
    await c.answer()

@dp.callback_query(lambda c: c.data == "main_menu")
async def process_main_menu(c: types.CallbackQuery):
    await c.message.edit_text(
        "Натисни кнопку:",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN_V2
    )
    await c.answer()

@dp.callback_query(lambda c: c.data == "get_combo")
async def process_get_combo(c: types.CallbackQuery):
    user_id = c.from_user.id
    admin_id = await _db.get_admin_id()
    is_admin = (user_id == admin_id) if admin_id else False

    # Перевіряємо глобальний доступ
    ga = await _db.get_setting('global_access')
    global_access = ga == '1'

    is_premium = await _db.is_user_premium(user_id)

    await c.answer()

    latest = await _db.get_latest_combo()
    prev = await _db.get_prev_combo()

    if global_access or is_premium or is_admin:
        if latest:
            # full combo for premium/users with access
            # latest may be a JSON list or plain text; ми зберігаємо як текст
            # припускаємо формат: JSON array або plain text
            try:
                data = json.loads(latest)
                # якщо список — відрендеримо красиво
                combo_list = data if isinstance(data, list) else [str(data)]
            except Exception:
                combo_list = [s.strip() for s in str(latest).split(',') if s.strip()]

            combo_text_list = []
            for i, card in enumerate(combo_list):
                combo_text_list.append(f"{i+1}. *{escape_markdown_v2(card)}*")

            today_date = escape_markdown_v2(datetime.utcnow().strftime("%d.%m.%Y"))
            response = (
                f"*Комбо на {today_date}*\n\n"
                f"Щоденний набір карток для отримання винагород:\n\n"
                f"{chr(10).join(combo_text_list)}\n\n"
                "_P.S.: збережено в архіві (преміум)_"
            )
            await c.message.answer(response, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await c.message.answer("Комбо ще не встановлено. Адмін, запустіть скрапінг або встановіть вручну.", parse_mode=ParseMode.MARKDOWN_V2)
    else:
        # Free preview logic: даємо 1 картку з latest (чи prev)
        if latest:
            try:
                data = json.loads(latest)
                combo_list = data if isinstance(data, list) else [str(data)]
            except Exception:
                combo_list = [s.strip() for s in str(latest).split(',') if s.strip()]

            preview_card = combo_list[0] if combo_list else None
            if preview_card:
                resp = (
                    f"*Безкоштовне прев'ю*\n\n"
                    f"Гра: *{escape_markdown_v2('невідомо')}*\n"
                    f"1 картка з сьогоднішнього сету: *{escape_markdown_v2(preview_card)}*\n\n"
                    "Щоб отримати весь сет карток і push-сповіщення — підписка $3/міс.\n"
                    "Натисни кнопку в описі або звернись до адміна."
                )
                await c.message.answer(resp, parse_mode=ParseMode.MARKDOWN_V2)
                return
        # якщо latest немає — даємо попереднє
        if prev:
            try:
                data = json.loads(prev)
                combo_list = data if isinstance(data, list) else [str(data)]
            except Exception:
                combo_list = [s.strip() for s in str(prev).split(',') if s.strip()]
            preview_card = combo_list[0] if combo_list else None
            if preview_card:
                resp = (
                    f"*Безкоштовне прев'ю (вчорашнє)*\n\n"
                    f"1 картка: *{escape_markdown_v2(preview_card)}*\n\n"
                    "Преміум = всі карти + push-сповіщення — $3/міс"
                )
                await c.message.answer(resp, parse_mode=ParseMode.MARKDOWN_V2)
                return

        # нічого не знайдено
        await c.message.answer("Комбо поки що немає. Спробуйте пізніше або напишіть адміну.", parse_mode=ParseMode.MARKDOWN_V2)

# Admin panel and commands
@dp.callback_query(lambda c: c.data == "admin_panel")
async def process_admin_panel(c: types.CallbackQuery, state: FSMContext):
    admin_id = await _db.get_admin_id()
    if not admin_id or c.from_user.id != admin_id:
        await c.answer("У вас немає доступу до панелі адміністратора.", show_alert=True)
        return
    await admin_panel(c, state)

async def admin_panel(c: types.CallbackQuery | types.Message, state: FSMContext) -> None:
    # similar to previous implementation but reads from DB
    if isinstance(c, types.CallbackQuery):
        await c.answer()
        message_to_edit = c.message
    else:
        message_to_edit = c

    latest = await _db.get_latest_combo()
    latest_text = escape_markdown_v2(latest) if latest else "Не встановлено"
    auto_url = await _db.get_auto_update_url()
    auto_url_disp = escape_markdown_v2(auto_url) if auto_url else "Не встановлено"

    text = (
        "*Панель адміністратора*\n\n"
        f"*Комбо (останнє):* `{latest_text}`\n"
        f"Поточний URL для автооновлення: {auto_url_disp}\n\n"
    )

    try:
        await message_to_edit.edit_text(text, reply_markup=await get_admin_keyboard(), parse_mode=ParseMode.MARKDOWN_V2)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.info("Admin panel unchanged")
        else:
            logging.exception("Помилка при редагуванні панелі адміна")

@dp.callback_query(lambda c: c.data == "toggle_global_access")
async def toggle_global_access(c: types.CallbackQuery):
    admin_id = await _db.get_admin_id()
    if not admin_id or c.from_user.id != admin_id:
        await c.answer("У вас немає доступу.", show_alert=True)
        return
    current = await _db.get_setting('global_access')
    new = '0' if current == '1' else '1'
    await _db.set_setting('global_access', new)
    await c.answer(f"Глобальний доступ: {'УВІМКНЕНО' if new=='1' else 'ВИМКНЕНО'}", show_alert=True)
    await admin_panel(c, None)

@dp.callback_query(lambda c: c.data == "set_combo_manual")
async def set_combo_manual(c: types.CallbackQuery):
    admin_id = await _db.get_admin_id()
    if not admin_id or c.from_user.id != admin_id:
        await c.answer("У вас немає доступу.", show_alert=True)
        return
    await c.message.edit_text("Введіть комбо у форматі JSON-масиву або списку через коми:\nНаприклад: [\"Card1\", \"Card2\", \"Card3\"] або Card1, Card2, Card3")
    await AdminState.SET_COMBO.set()
    await c.answer()

@dp.message(AdminState.SET_COMBO)
async def process_set_combo(message: types.Message, state: FSMContext):
    admin_id = await _db.get_admin_id()
    if not admin_id or message.from_user.id != admin_id:
        return
    text = message.text.strip()
    # Підтримуємо JSON-масив або CSV
    combo_list = None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            combo_list = [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        # спробуємо CSV
        combo_list = [s.strip() for s in text.split(',') if s.strip()]

    if not combo_list or len(combo_list) == 0:
        await message.answer("Помилка: не вдалось розпізнати комбо. Спробуйте ще раз.")
        return

    # зберігаємо як JSON
    await _db.set_latest_combo(json.dumps(combo_list, ensure_ascii=False))
    await message.answer(f"✅ Комбо оновлено: {escape_markdown_v2(', '.join(combo_list))}", parse_mode=ParseMode.MARKDOWN_V2)
    await state.clear()
    await admin_panel(message, state)

@dp.callback_query(lambda c: c.data == "set_auto_url")
async def set_auto_url(c: types.CallbackQuery):
    admin_id = await _db.get_admin_id()
    if not admin_id or c.from_user.id != admin_id:
        await c.answer("У вас немає доступу.", show_alert=True)
        return
    await c.message.edit_text("Введіть URL для автооновлення (або напишіть 'Н/Д' щоб вимкнути):")
    await AdminState.SET_URL.set()
    await c.answer()

@dp.message(AdminState.SET_URL)
async def process_set_url(message: types.Message, state: FSMContext):
    admin_id = await _db.get_admin_id()
    if not admin_id or message.from_user.id != admin_id:
        return
    url = message.text.strip()
    if url.lower() in ('н/д', 'нд', 'none'):
        await _db.set_auto_update_url(None)
        await message.answer("✅ Автооновлення вимкнено.")
    elif not (url.startswith('http://') or url.startswith('https://')):
        await message.answer("Помилка: URL має починатися з http:// або https://")
        return
    else:
        await _db.set_auto_update_url(url)
        await message.answer(f"✅ URL для автооновлення встановлено: {escape_markdown_v2(url)}", parse_mode=ParseMode.MARKDOWN_V2)
    await state.clear()
    await admin_panel(message, state)

@dp.callback_query(lambda c: c.data == "force_fetch_combo")
async def force_fetch_combo(c: types.CallbackQuery):
    admin_id = await _db.get_admin_id()
    if not admin_id or c.from_user.id != admin_id:
        await c.answer("У вас немає доступу.", show_alert=True)
        return
    await c.answer("Запускаю скрапінг комбо...", show_alert=False)

    if not SCRAPER_AVAILABLE:
        await c.message.answer("❌ Скрапер недоступний. Перевірте hamster_scraper.py")
        return

    try:
        # Виконуємо скрапінг в окремому потоці (якщо scraper sync)
        new_combo = await asyncio.to_thread(_scrape_for_combo)
        # Очікуємо, що new_combo — або список, або порожній
        if new_combo and isinstance(new_combo, list) and len(new_combo) > 0:
            await _db.set_latest_combo(json.dumps(new_combo, ensure_ascii=False))
            await c.message.answer(f"✅ Комбо оновлено скрапером: {escape_markdown_v2(', '.join(new_combo))}", parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await c.message.answer("❌ Скрапінг не знайшов нового комбо.")
    except Exception as e:
        logging.exception("Помилка під час скрапінгу")
        await c.message.answer(f"❌ Помилка під час скрапінгу: {escape_markdown_v2(str(e))}")

# ---------------------------------------
# Webhook handler (для deployment)
# ---------------------------------------
async def handle_webhook(request: web.Request):
    token = request.match_info.get('token')
    if token != TOKEN:
        return web.Response(status=403)
    bot = request.app['bot']
    dp = request.app['dp']
    data = await request.json()
    update = types.Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return web.Response(status=200)

# ---------------------------------------
# Startup / Shutdown
# ---------------------------------------
async def on_startup(bot: Bot):
    if IS_WEBHOOK:
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
        logging.info(f"Webhook set to {WEBHOOK_URL}")
    # Запускаємо скрапер якщо є
    if SCRAPER_AVAILABLE:
        asyncio.create_task(scraper_main_scheduler())
    logging.info("Bot started")

async def on_shutdown(bot: Bot):
    if IS_WEBHOOK:
        await bot.delete_webhook()

# ---------------------------------------
# Main launcher
# ---------------------------------------
def main_polling():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    logging.info("Starting polling...")
    try:
        asyncio.run(dp.start_polling(bot))
    except KeyboardInterrupt:
        logging.info("Shutdown requested")


def main_webhook():
    app = web.Application()
    app['bot'] = bot
    app['dp'] = dp
    app.router.add_post(f"/webhook/{TOKEN}", handle_webhook)
    app.on_startup.append(lambda a: on_startup(bot))
    app.on_shutdown.append(lambda a: on_shutdown(bot))
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

# ---------------------------------------
# Запуск
# ---------------------------------------
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    if IS_WEBHOOK:
        main_webhook()
    else:
        main_polling()

# TODO:
# - додати endpoint для remote auto-update (secure token)
# - інтегрувати реальні платіжні шлюзи (CryptoBot / TON)
# - додати healthcheck & metrics
# - додати unit tests для parser'а
