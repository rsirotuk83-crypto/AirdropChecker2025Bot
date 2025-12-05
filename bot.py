import os
import asyncio
import json
import logging
import httpx
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

# Встановлюємо рівень логування.
# Цей лог буде видно у вкладці Deploy Logs на Railway.
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Обов'язково перевіряйте, чи ADMIN_ID дійсно встановлений
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (ValueError, TypeError):
    logging.error("КРИТИЧНА ПОМИЛКА: Змінна оточення ADMIN_ID не встановлена або некоректна.")
    ADMIN_ID = 0 # Defaulting to 0 if not set, preventing admin access

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# --- Налаштування Постійного Сховища (Volume) ---
# Цей шлях повинен збігатися з налаштуванням у railway.toml
DATA_DIR = "/app/data"
DB_PATH = os.path.join(DATA_DIR, "db.json")

# Створюємо директорію, якщо вона не існує (це обов'язково для Railway Volume)
try:
    os.makedirs(DATA_DIR, exist_ok=True)
    logging.info(f"Сховище ініціалізовано: {DATA_DIR}")
except Exception as e:
    logging.error(f"Помилка створення директорії {DATA_DIR}: {e}")

subs = {}
active = False
combo_text = "Комбо ще не встановлено"
source_url = ""

def load():
    """Завантажує дані з постійного сховища."""
    global subs, active, combo_text, source_url
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
                subs = {int(k): v for k, v in d.get("subs", {}).items()}
                active = d.get("active", False)
                combo_text = d.get("combo", combo_text)
                source_url = d.get("url", "")
            logging.info(f"Дані завантажено. Активність: {active}, Преміум-користувачів: {len(subs)}")
        except json.JSONDecodeError:
            logging.warning("Файл db.json порожній або пошкоджений. Створюємо новий.")
            save()
        except Exception as e:
            logging.error(f"Помилка завантаження db.json: {e}")
    else:
        logging.info("Файл db.json не знайдено. Створюємо новий.")
        save()


def save():
    """Зберігає дані до постійного сховища."""
    data = {"subs": subs, "active": active, "combo": combo_text, "url": source_url}
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info("Дані успішно збережено.")
    except Exception as e:
        logging.error(f"Помилка збереження db.json: {e}")

# Завантажуємо стан при старті
load()

# --- Автооновлення Комбо ---
async def fetch():
    """Виконує HTTP-запит для оновлення комбо-тексту."""
    global combo_text, source_url
    if not source_url: 
        logging.warning("URL для оновлення не встановлено.")
        return
        
    logging.info(f"Спроба оновлення комбо з {source_url}")
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(source_url, timeout=15)
            r.raise_for_status() # Викликає виняток для кодів 4xx/5xx
            
            new_combo_text = r.text.strip()
            if new_combo_text != combo_text:
                combo_text = new_combo_text
                save()
                await bot.send_message(ADMIN_ID, "✅ Комбо оновлено автоматично!")
                logging.info("Комбо оновлено.")
            else:
                logging.info("Комбо не потребує оновлення.")
                
    except httpx.RequestError as e:
        error_msg = f"Помилка запиту HTTP: {e}"
        logging.error(error_msg)
        if ADMIN_ID != 0: await bot.send_message(ADMIN_ID, error_msg)
    except Exception as e:
        error_msg = f"Невідома помилка оновлення: {e}"
        logging.error(error_msg)
        if ADMIN_ID != 0: await bot.send_message(ADMIN_ID, error_msg)

async def scheduler():
    """Планувальник для запуску оновлення."""
    # Чекаємо 30 секунд після запуску, щоб бот встиг повністю завантажитися
    await asyncio.sleep(30)
    # Перше оновлення
    await fetch()
    while True:
        # Чекаємо 24 години
        await asyncio.sleep(24 * 3600)
        await fetch()

# --- ХЕНДЛЕРИ ---

@dp.message(CommandStart())
async def start(m: types.Message):
    """Обробник команди /start."""
    uid = m.from_user.id
    logging.info(f"Отримано /start від користувача {uid}")
    
    kb = [[types.InlineKeyboardButton(text="Отримати комбо", callback_data="combo")]]
    
    if uid == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="⚙️ Адмінка", callback_data="admin")])
        
    text = f"Привіт, {m.from_user.full_name}!\n\nЛаскаво просимо до @CryptoComboDaily.\nНатисни кнопку нижче:"
    
    await m.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))


@dp.callback_query(F.data == "combo")
async def get_combo(c: types.CallbackQuery):
    """Обробник натискання кнопки 'Отримати комбо'."""
    uid = c.from_user.id
    logging.info(f"Отримано callback 'combo' від користувача {uid}. Активно: {active}, Premium: {uid in subs}")
    
    if uid == ADMIN_ID or active or uid in subs:
        t = f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo_text}"
        
        # Спроба відредагувати повідомлення
        try:
            await c.message.edit_text(t, reply_markup=c.message.reply_markup)
            await c.answer() # Закриваємо сповіщення, щоб кнопка не виглядала натиснутою
        except TelegramBadRequest as e:
            # Це нормально, якщо текст не змінився, Telegram видає помилку
            if "message is not modified" in str(e):
                await c.answer("Комбо вже відображено.", show_alert=False)
            else:
                logging.error(f"Помилка редагування повідомлення: {e}")
                await c.answer("Помилка відображення.", show_alert=True)
                
    else:
        await c.answer("❌ Тільки для преміум-користувачів.", show_alert=True)


@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    """Обробник панелі адміністратора."""
    if c.from_user.id != ADMIN_ID:
        await c.answer("Недостатньо прав.")
        return
        
    logging.info(f"Адміністратор {c.from_user.id} відкрив панель.")
    
    status = "АКТИВНО ✅" if active else "НЕАКТИВНО ❌"
    
    kb = [
        [types.InlineKeyboardButton(text="Оновити зараз", callback_data="force")],
        [types.InlineKeyboardButton(text=f"Глобальне Комбо: {status}", callback_data="toggle_active")],
        [types.InlineKeyboardButton(text="Повернутися", callback_data="back_to_start")]
    ]
    
    await c.message.edit_text(
        f"⚙️ <b>Адмін-панель</b>\n\nПоточний URL: <code>{source_url or 'Не встановлено'}</code>", 
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await c.answer()


@dp.callback_query(F.data.in_({"force", "toggle_active", "back_to_start"}))
async def admin_actions(c: types.CallbackQuery):
    """Обробник дій адміністратора."""
    if c.from_user.id != ADMIN_ID: return
    
    logging.info(f"Адмін-дія: {c.data}")
    
    if c.data == "force":
        await c.answer("Розпочато примусове оновлення...")
        await fetch() # Запускаємо оновлення
        await c.message.edit_text(c.message.text) # Оновлюємо, щоб зняти напис "Оновлення..."
        
    elif c.data == "toggle_active":
        global active
        active = not active
        save()
        
        # Повертаємо користувача на оновлену адмін-панель
        await admin_panel(c)
        
    elif c.data == "back_to_start":
        await c.answer()
        # Повертаємось до початкового повідомлення
        await start(c.message)


# --- Адмін-команди ---

@dp.message(F.text.startswith("/seturl"))
async def seturl(m: types.Message):
    """Команда для встановлення URL для оновлення комбо."""
    if m.from_user.id != ADMIN_ID: return
    
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        await m.answer("Використання: /seturl https://...")
        return
        
    global source_url
    source_url = parts[1].strip()
    save()
    
    await m.answer(f"URL збережено:\n<code>{source_url}</code>", parse_mode="HTML")
    logging.info(f"URL оновлення встановлено на: {source_url}")


@dp.message(F.text.startswith("/setcombo"))
async def setcombo(m: types.Message):
    """Команда для ручного встановлення комбо-тексту."""
    if m.from_user.id != ADMIN_ID: return
    
    global combo_text
    # Використовуємо partition для отримання всього тексту після команди
    combo_text = m.text.partition(" ")[2].strip()
    
    if not combo_text:
        await m.answer("Використання: /setcombo Новий текст комбо...")
        return
        
    save()
    await m.answer(f"Комбо збережено:\n{combo_text}")
    logging.info("Комбо-текст оновлено вручну.")


# --- Запуск ---

async def main():
    """Головна функція запуску бота."""
    logging.info("БОТ ЗАПУЩЕНО — Створюємо планувальник і починаємо Polling.")
    
    # Створюємо завдання планувальника, щоб воно працювало паралельно з ботом
    asyncio.create_task(scheduler())
    
    # Видаляємо всі встановлені WebHooks (це критично важливо, якщо ви перейшли з WebHook на Polling)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logging.warning(f"Не вдалося видалити WebHook: {e}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот зупинено вручну.")
    except Exception as e:
        logging.error(f"Критична помилка запуску: {e}")
