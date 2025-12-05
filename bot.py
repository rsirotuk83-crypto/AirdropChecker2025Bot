import os
import asyncio
import json
import logging
import httpx
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest, TelegramConflictError

# --- Налаштування Логування ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Змінні Оточення ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (ValueError, TypeError):
    logging.error("КРИТИЧНА ПОМИЛКА: ADMIN_ID не встановлено або некоректне. Адмін-функції вимкнено.")
    ADMIN_ID = 0

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# --- Налаштування Постійного Сховища ---
# Шлях до директорії, яка монтується на Volume Railway
DATA_DIR = "/app/data" 
DB_PATH = os.path.join(DATA_DIR, "db.json")
os.makedirs(DATA_DIR, exist_ok=True) 

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
                # Перетворюємо ключі (id користувачів) на цілі числа
                subs = {int(k): v for k, v in d.get("subs", {}).items()} 
                active = d.get("active", False)
                combo_text = d.get("combo", combo_text)
                source_url = d.get("url", "")
            logging.info(f"Дані завантажено. Активність: {active}, Преміум-користувачів: {len(subs)}")
        except (json.JSONDecodeError, FileNotFoundError):
            logging.warning("Файл db.json не знайдено або пошкоджений. Створюємо новий.")
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
            r.raise_for_status()
            
            new_combo_text = r.text.strip()
            if new_combo_text != combo_text:
                combo_text = new_combo_text
                save()
                if ADMIN_ID != 0: await bot.send_message(ADMIN_ID, "✅ Комбо оновлено автоматично!")
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
    """Планувальник для запуску оновлення (раз на добу)."""
    await asyncio.sleep(30) # Перший запуск через 30 секунд
    await fetch()
    while True:
        await asyncio.sleep(24 * 3600) # Чекаємо 24 години
        await fetch()

# --- ХЕНДЛЕРИ ---

def get_start_keyboard(is_admin: bool):
    """Створює клавіатуру для команди /start."""
    kb = [[types.InlineKeyboardButton(text="Отримати комбо", callback_data="combo")]]
    
    if is_admin:
        kb.append([types.InlineKeyboardButton(text="⚙️ Адмінка", callback_data="admin")])
        
    return types.InlineKeyboardMarkup(inline_keyboard=kb)


@dp.message(CommandStart())
async def start(m: types.Message):
    """Обробник команди /start."""
    uid = m.from_user.id
    logging.info(f"Отримано /start від користувача {uid}")
    
    kb = get_start_keyboard(uid == ADMIN_ID)
        
    text = f"Привіт, {m.from_user.full_name}!\n\nЛаскаво просимо.\nНатисни кнопку нижче:"
    
    await m.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "combo")
async def get_combo(c: types.CallbackQuery):
    """Обробник натискання кнопки 'Отримати комбо'."""
    uid = c.from_user.id
    
    if uid == ADMIN_ID or active or uid in subs:
        t = f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo_text}"
        
        try:
            # Використовуємо стару клавіатуру, щоб була можливість повернутися на /start
            kb = get_start_keyboard(uid == ADMIN_ID) 
            await c.message.edit_text(t, parse_mode="HTML", reply_markup=kb)
            await c.answer()
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await c.answer("Комбо вже відображено.", show_alert=False)
            else:
                logging.error(f"Помилка редагування повідомлення: {e}")
                await c.answer("Помилка відображення.", show_alert=True)
                
    else:
        await c.answer("❌ Тільки для преміум-користувачів.", show_alert=True)


async def send_admin_panel(c: types.CallbackQuery):
    """Спільна функція для відображення адмін-панелі."""
    status = "АКТИВНО ✅" if active else "НЕАКТИВНО ❌"
    
    kb = [
        [types.InlineKeyboardButton(text="Оновити зараз (fetch)", callback_data="force")],
        [types.InlineKeyboardButton(text=f"Глобальне Комбо: {status}", callback_data="toggle_active")],
        [types.InlineKeyboardButton(text="Назад до /start", callback_data="back_to_start")]
    ]
    
    await c.message.edit_text(
        f"⚙️ <b>Адмін-панель</b>\n\nПоточний URL: <code>{source_url or 'Не встановлено'}</code>", 
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await c.answer()

@dp.callback_query(F.data == "admin")
async def admin_panel_handler(c: types.CallbackQuery):
    """Обробник входу в панель адміністратора."""
    if c.from_user.id != ADMIN_ID:
        await c.answer("Недостатньо прав.")
        return
    await send_admin_panel(c)


@dp.callback_query(F.data == "force")
async def admin_force_fetch(c: types.CallbackQuery):
    """Обробник примусового оновлення."""
    if c.from_user.id != ADMIN_ID: return
    await c.answer("Розпочато примусове оновлення...")
    await fetch() 
    await send_admin_panel(c)

@dp.callback_query(F.data == "toggle_active")
async def admin_toggle_active(c: types.CallbackQuery):
    """Обробник перемикання глобальної активності."""
    if c.from_user.id != ADMIN_ID: return
    global active
    active = not active
    save()
    await send_admin_panel(c)
    
@dp.callback_query(F.data == "back_to_start")
async def admin_back_to_start(c: types.CallbackQuery):
    """Обробник повернення на /start."""
    if c.from_user.id != ADMIN_ID: return
    
    # Використовуємо edit_text, щоб повернути повідомлення до стану /start
    text = f"Привіт, {c.from_user.full_name}!\n\nЛаскаво просимо.\nНатисни кнопку нижче:"
    kb = get_start_keyboard(True) # Адмін завжди true тут
    
    try:
        await c.message.edit_text(text, reply_markup=kb)
        await c.answer("Повернення до головного меню.", show_alert=False)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
             await c.answer("Ви вже в головному меню.", show_alert=False)
        else:
            logging.error(f"Помилка повернення: {e}")
            await c.answer("Помилка повернення до меню.", show_alert=True)
            
            
# --- Адмін-команди для /seturl та /setcombo ---

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
    
    combo_text_input = m.text.partition(" ")[2].strip()
    
    if not combo_text_input:
        await m.answer("Використання: /setcombo Новий текст комбо...")
        return
        
    global combo_text
    combo_text = combo_text_input
    save()
    await m.answer(f"Комбо збережено:\n{combo_text}")


# --- Головний Запуск (КЛЮЧОВЕ ВИПРАВЛЕННЯ КОНФЛІКТУ) ---

async def main():
    """Головна функція запуску бота."""
    
    # !!! ВИПРАВЛЕННЯ КОНФЛІКТУ: ВИДАЛЯЄМО WEBHOOK, щоб Polling працював !!! 
    try:
        logging.info("Спроба видалення WebHook та очищення оновлень...")
        # drop_pending_updates=True гарантує, що бот почне приймати нові оновлення
        await bot.delete_webhook(drop_pending_updates=True) 
        logging.info("WebHook успішно видалено. Система готова до Polling.")
    except Exception as e:
        logging.warning(f"Помилка при видаленні WebHook (це нормально, якщо його не було): {e}")

    logging.info("БОТ ЗАПУЩЕНО — Створюємо планувальник і починаємо Polling.")
    
    # Запускаємо планувальник для періодичного оновлення комбо
    asyncio.create_task(scheduler())
    
    # Починаємо Polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except TelegramConflictError:
        logging.critical("Критична помилка: Конфлікт Polling. Переконайтеся, що запущено лише 1 екземпляр!")
    except KeyboardInterrupt:
        logging.info("Бот зупинено вручну.")
    except Exception as e:
        logging.error(f"Критична помилка запуску: {e}")
