import os
import asyncio
import json
import logging
import httpx
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest # Додано для обробки помилок редагування

# --- Налаштування Логування ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Змінні Оточення ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (ValueError, TypeError):
    logging.error("КРИТИЧНА ПОМИЛКА: Змінна оточення ADMIN_ID не встановлена або некоректна. Адмін-функції вимкнено.")
    ADMIN_ID = 0

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# --- Налаштування Постійного Сховища ---
DATA_DIR = "/app/data"
DB_PATH = os.path.join(DATA_DIR, "db.json")

try:
    os.makedirs(DATA_DIR, exist_ok=True)
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
    # Чекаємо 30 секунд, щоб бот встиг повністю завантажитися і видалити WebHook
    await asyncio.sleep(30) 
    await fetch() # Перше оновлення
    while True:
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
        
        try:
            # Редагуємо повідомлення, щоб оновити дату та уникнути повторного натискання
            await c.message.edit_text(t, parse_mode="HTML", reply_markup=c.message.reply_markup)
            await c.answer() # Закриваємо сповіщення
        except TelegramBadRequest as e:
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
        [types.InlineKeyboardButton(text="Оновити зараз (fetch)", callback_data="force")],
        [types.InlineKeyboardButton(text=f"Глобальне Комбо: {status}", callback_data="toggle_active")],
        [types.InlineKeyboardButton(text="Повернутися", callback_data="back_to_start")]
    ]
    
    await c.message.edit_text(
        f"⚙️ <b>Адмін-панель</b>\n\nПоточний URL: <code>{source_url or 'Не встановлено'}</code>", 
        parse_mode="HTML",
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
        await fetch() 
        # Оновлюємо панель, щоб показати, що дія виконана
        await admin_panel(c)
        
    elif c.data == "toggle_active":
        global active
        active = not active
        save()
        await admin_panel(c)
        
    elif c.data == "back_to_start":
        await c.answer()
        # Створюємо фейкове повідомлення, щоб запустити start
        fake_message = types.Message(message_id=c.message.message_id, date=datetime.now(), chat=c.message.chat, text="/start")
        await start(fake_message)


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


@dp.message(F.text.startswith("/setcombo"))
async def setcombo(m: types.Message):
    """Команда для ручного встановлення комбо-тексту."""
    if m.from_user.id != ADMIN_ID: return
    
    global combo_text
    combo_text = m.text.partition(" ")[2].strip()
    
    if not combo_text:
        await m.answer("Використання: /setcombo Новий текст комбо...")
        return
        
    save()
    await m.answer(f"Комбо збережено:\n{combo_text}")


# --- Запуск ---

async def main():
    """Головна функція запуску бота."""
    logging.info("БОТ ЗАПУЩЕНО — Створюємо планувальник і починаємо Polling.")
    
    # !!! КРИТИЧНО ВАЖЛИВО !!! Видалення WebHook для коректної роботи Polling
    try:
        logging.info("Спроба видалення WebHook...")
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("WebHook успішно видалено.")
    except Exception as e:
        logging.warning(f"Не вдалося видалити WebHook: {e}. Це може бути нормально, якщо його не було.")

    # Створюємо завдання планувальника, щоб воно працювало паралельно з ботом
    asyncio.create_task(scheduler())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот зупинено вручну.")
    except Exception as e:
        logging.error(f"Критична помилка запуску: {e}")
