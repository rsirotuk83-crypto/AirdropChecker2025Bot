import os
import asyncio
import json
import logging
import httpx
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramConflictError

# === Налаштування логування ===
# Використовуємо коректний формат логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === Змінні середовища (Токен і Адмін) ===
# BOT_TOKEN та ADMIN_ID беруться зі змінних середовища Railway.
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# Перевірка токена
if not BOT_TOKEN:
    logging.critical("Помилка: не встановлено BOT_TOKEN. Бот не може запуститися.")
    exit(1)

# Перетворення ADMIN_ID
try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else 0
except ValueError:
    logging.critical("Помилка: ADMIN_ID некоректне (не число). Адмін-функції вимкнено.")
    ADMIN_ID = 0

if not ADMIN_ID:
    logging.warning("ПОПЕРЕДЖЕННЯ: ADMIN_ID не встановлено. Адмін-функції не будуть доступні.")


# Ініціалізація бота та диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# === Конфігурація Persistent Volume ===
# Шлях, який монтується до постійного Volume на Railway
DATA_DIR = "/app/data"
DB_PATH = os.path.join(DATA_DIR, "db.json")

# Створення директорії, якщо її немає (для першого запуску)
os.makedirs(DATA_DIR, exist_ok=True)
logging.info(f"Перевірено або створено директорію даних: {DATA_DIR}")

# === Стан (буде завантажено з db.json) ===
subs = {}           # Преміум-користувачі (ID -> True)
active = False      # Глобальний доступ (boolean)
combo_text = "Комбо ще не встановлено. Адміністратор, встановіть його командою /setcombo або /seturl."
source_url = ""     # URL для автооновлення

# === Функції Завантаження / Збереження ===
def load():
    """Завантажує дані з db.json."""
    global subs, active, combo_text, source_url
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
                # Конвертуємо ключі назад у int
                subs = {int(k): v for k, v in d.get("subs", {}).items()}
                active = d.get("active", False)
                combo_text = d.get("combo", combo_text)
                source_url = d.get("url", "")
            logging.info("Дані успішно завантажено з Volume.")
        except Exception as e:
            logging.error(f"Помилка читання даних з {DB_PATH}: {e}")
    else:
        logging.warning(f"Файл бази даних {DB_PATH} не знайдено. Будуть використані початкові значення.")

def save():
    """Зберігає дані у db.json."""
    data = {"subs": subs, "active": active, "combo": combo_text, "url": source_url}
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.debug("Дані успішно збережено.")
    except Exception as e:
        logging.error(f"Помилка збереження даних у {DB_PATH}: {e}")

# Завантажуємо дані при запуску
load()

# Автоматичне додавання ADMIN_ID до Premium, якщо його немає
if ADMIN_ID and ADMIN_ID not in subs:
    subs[ADMIN_ID] = True
    save()
    logging.info(f"Адмін ID {ADMIN_ID} додано до Premium.")

# === Логіка Автооновлення ===
async def fetch():
    """Завантажує та оновлює комбо з source_url."""
    global combo_text
    if not source_url:
        logging.warning("URL для автооновлення відсутній.")
        if ADMIN_ID:
             await bot.send_message(ADMIN_ID, "⚠️ URL для автооновлення не встановлено. Використайте /seturl.")
        return
    
    logging.info(f"Запуск автооновлення з URL: {source_url}")
    try:
        # Використовуємо httpx для асинхронного запиту
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(source_url)
            
            if r.status_code == 200:
                new = r.text.strip()
                if new and new != combo_text:
                    combo_text = new
                    save()
                    if ADMIN_ID:
                        await bot.send_message(ADMIN_ID, "✅ Комбо автоматично оновлено!")
                    logging.info("Комбо успішно оновлено з URL.")
                else:
                    logging.info("Комбо не змінилося або отримано порожній вміст.")
            else:
                if ADMIN_ID:
                    await bot.send_message(ADMIN_ID, f"❌ Помилка: URL повернув статус {r.status_code}")
                logging.error(f"Помилка: URL повернув статус {r.status_code}")
                
    except Exception as e:
        if ADMIN_ID:
            error_msg = f"❌ Критична Помилка автооновлення:\n{type(e).__name__}: {e}"
            await bot.send_message(ADMIN_ID, error_msg)
        logging.error(f"Критична Помилка автооновлення: {e}")

async def scheduler():
    """Планувальник для запуску fetch() кожні 24 години."""
    # Чекаємо 10 секунд для стабільного запуску бота, потім виконуємо перший fetch
    await asyncio.sleep(10) 
    await fetch()
    while True:
        await asyncio.sleep(24 * 3600) # Чекаємо 24 години
        await fetch()

# === Хендлери: Start and Combo ===
@dp.message(CommandStart())
async def start_handler(m: types.Message):
    """Обробка команди /start."""
    uid = m.from_user.id
    
    # Головна кнопка для отримання комбо
    kb = [[types.InlineKeyboardButton(text="Отримати комбо 🔑", callback_data="combo")]]
    
    # Додаємо кнопку Адмінки, якщо користувач - адмін
    if uid == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="⚙️ Адмінка", callback_data="admin_panel")])
        
    await m.answer(
        f"Привіт! Ваш ID: <code>{uid}</code>\nНатисніть кнопку:", 
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(F.data == "combo")
async def show_combo(c: types.CallbackQuery):
    """Показ комбо за умови наявності доступу."""
    uid = c.from_user.id
    
    # Перевірка доступу
    has_access = (uid == ADMIN_ID) or active or subs.get(uid, False)
    
    if has_access:
        t = f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo_text}"
        await c.message.edit_text(t, parse_mode="HTML")
    else:
        # Використовуємо c.answer для повідомлення користувачу без модального вікна
        await c.answer("❌ Комбо доступне лише для преміум-користувачів або при глобальній активації.", show_alert=True)

# === Хендлери: Admin Panel ===
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(c: types.CallbackQuery):
    """Головна панель адміністратора."""
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Недостатньо прав.")
        
    global_status = "✅ АКТИВНО" if active else "❌ ВИМКНЕНО"
    # Фільтруємо адміна, якщо він був у subs
    premium_count = len([uid for uid in subs if subs[uid] and uid != ADMIN_ID])
    
    kb = [
        [types.InlineKeyboardButton(text="🔄 Оновити комбо зараз", callback_data="force_fetch_combo")],
        [types.InlineKeyboardButton(text=f"Глобальний доступ: {global_status}", callback_data="toggle_active")],
        [types.InlineKeyboardButton(text=f"Управління Premium ({premium_count} users)", callback_data="admin_premium")]
    ]
    
    await c.message.edit_text(
        f"⚙️ *Панель адміністратора*\n\n"
        f"Поточний URL для оновлення: <code>{source_url or 'Не встановлено'}</code>\n",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(F.data == "toggle_active")
async def toggle_active(c: types.CallbackQuery):
    """Перемикає статус глобальної активності."""
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Недостатньо прав.")
    
    global active
    active = not active
    save()
    
    status_msg = "Глобальний доступ Увімкнено для всіх!" if active else "Глобальний доступ Вимкнено."
    await c.answer(status_msg)
    await admin_panel(c) # Оновлюємо панель

@dp.callback_query(F.data == "force_fetch_combo")
async def force_fetch_combo(c: types.CallbackQuery):
    """Примусово запускає оновлення комбо."""
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Недостатньо прав.")
    
    # Намагаємося оновити комбо
    await fetch()
    
    # Оскільки fetch() може відправити повідомлення про помилку, просто оновлюємо панель.
    await c.answer("Оновлення ініційовано!")
    await admin_panel(c)
    
@dp.callback_query(F.data == "admin_premium")
async def admin_premium_panel(c: types.CallbackQuery):
    """Панель управління Premium користувачами."""
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Недостатньо прав.")
        
    premium_list = "\n".join([f"• <code>{uid}</code>" for uid in subs if subs[uid] and uid != ADMIN_ID])
    
    kb = [
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")],
    ]
    
    await c.message.edit_text(
        f"🔐 *Управління Premium Users*\n\n"
        f"Для додавання/видалення використовуйте команди:\n"
        f"<code>/addsub ID_КОРИСТУВАЧА</code>\n"
        f"<code>/delsub ID_КОРИСТУВАЧА</code>\n\n"
        f"**Активні Premium IDs:**\n{premium_list or 'Список порожній'}",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
    )

# === Функція для парсингу ID ===
def parse_uid_from_command(text: str) -> int | None:
    """Витягує ID користувача з тексту команди."""
    try:
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            return int(parts[1].strip())
        return None
    except ValueError:
        return None

# === Admin Commands: Subscription Management ===
@dp.message(F.text.startswith("/addsub"))
async def add_subscription(m: types.Message):
    """Додає користувача до Premium-списку."""
    if m.from_user.id != ADMIN_ID:
        return
    
    target_uid = parse_uid_from_command(m.text)
    if not target_uid:
        return await m.answer("❌ Використання: <code>/addsub ID_КОРИСТУВАЧА</code>")
        
    subs[target_uid] = True
    save()
    await m.answer(f"✅ Користувача <code>{target_uid}</code> додано до Premium.")

@dp.message(F.text.startswith("/delsub"))
async def delete_subscription(m: types.Message):
    """Видаляє користувача з Premium-списку."""
    if m.from_user.id != ADMIN_ID:
        return
    
    target_uid = parse_uid_from_command(m.text)
    if not target_uid:
        return await m.answer("❌ Використання: <code>/delsub ID_КОРИСТУВАЧА</code>")

    if target_uid in subs:
        del subs[target_uid]
        save()
        await m.answer(f"✅ Користувача <code>{target_uid}</code> видалено з Premium.")
    else:
        await m.answer(f"⚠️ Користувача <code>{target_uid}</code> не знайдено у Premium-списку.")

# === Admin Commands: Content Management ===
@dp.message(F.text.startswith("/seturl"))
async def seturl(m: types.Message):
    """Встановлює URL для автоматичного оновлення."""
    if m.from_user.id != ADMIN_ID:
        return
    try:
        global source_url
        url = m.text.split(maxsplit=1)[1].strip()
        if not url.startswith("http"):
            raise ValueError("Некоректний URL")
        source_url = url
        save()
        await m.answer(f"✅ URL для автооновлення збережено:\n<code>{source_url}</code>")
    except:
        await m.answer("❌ Використання: <code>/seturl https://products.aspose.app/words/ru/viewer/txt</code>")

@dp.message(F.text.startswith("/setcombo"))
async def setcombo(m: types.Message):
    """Встановлює комбо вручну."""
    if m.from_user.id != ADMIN_ID:
        return
    global combo_text
    new_combo = m.text.partition(" ")[2].strip()
    if new_combo:
        combo_text = new_combo
        save()
        await m.answer("✅ Комбо вручну збережено.")
    else:
        await m.answer("❌ Використання: <code>/setcombo [Новий текст комбо]</code>")

# === Main Startup Function ===
async def main():
    """Основна функція запуску бота."""
    # Запускаємо планувальник як фонову задачу
    asyncio.create_task(scheduler()) 
    
    logging.info("БОТ УСПІШНО ЗАПУЩЕНО — ПОЧИНАЄМО ПОЛЛІНГ")
    
    try:
        await dp.start_polling(bot)
    except TelegramConflictError:
        logging.error("Конфлікт Polling: Бот вже запущений в іншому місці.")
    except Exception as e:
        logging.critical(f"Критична помилка при запуску: {e}")

if __name__ == "__main__":
    try:
        # Встановлюємо максимальний таймаут для закриття, щоб уникнути помилок в логах Railway
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот зупинено вручну.")
    except Exception as e:
        logging.critical(f"Помилка виконання asyncio: {e}")
