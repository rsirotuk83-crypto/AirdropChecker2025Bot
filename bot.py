import os
import asyncio
import logging
import json
import httpx
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

logging.basicConfig(level=logging.INFO)

# --- КОНФІГУРАЦІЯ ---
# Використовуємо .env або змінні середовища для надійності
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Обов'язково переконайтеся, що ADMIN_ID встановлено (наприклад, у .env файлі)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) 

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === ГЛОБАЛЬНІ ДАНІ ===
combo_text = "Комбо ще не встановлено. Спробуйте оновити пізніше."
source_url = ""

# === АВТООНОВЛЕННЯ З HTTP-ДЖЕРЕЛА ===
async def fetch():
    global combo_text
    # Перевірка наявності URL
    if not source_url:
        logging.warning("source_url не встановлено. Автооновлення пропущено.")
        return
    
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(source_url)
            r.raise_for_status() # Викликає виняток для кодів 4xx/5xx
            
            new = r.text.strip()
            
            if new and new != combo_text:
                combo_text = new
                logging.info(f"Комбо оновлено: {new[:50]}...")
                if ADMIN_ID:
                    await bot.send_message(ADMIN_ID, "✅ Комбо автоматично оновлено!")
            elif not new:
                 logging.warning("Отримано порожній контент з джерела.")
            else:
                 logging.info("Комбо не змінилося.")

    except httpx.HTTPStatusError as e:
        error_msg = f"Помилка HTTP: Статус {e.response.status_code} при запиті до {source_url}"
        logging.error(error_msg)
        if ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"❌ Помилка автооновлення: {error_msg}")
    except Exception as e:
        error_msg = f"Критична помилка автооновлення: {e.__class__.__name__}: {e}"
        logging.error(error_msg)
        if ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"❌ Критична помилка: {e}")

async def scheduler():
    # Запуск першої перевірки через 30 секунд, потім раз на добу
    await asyncio.sleep(30)
    while True:
        logging.info("Планувальник: Запуск оновлення комбо...")
        await fetch()
        await asyncio.sleep(24 * 3600) # 24 години

# === ХЕНДЛЕРИ КОМАНД І КНОПОК ===

@dp.message(CommandStart())
async def start(m: types.Message):
    # Обов'язково створюйте нову клавіатуру, щоб не редагувати старі
    kb = [[types.InlineKeyboardButton(text="🎁 Отримати комбо", callback_data="combo")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="🛠 Адмінка", callback_data="admin")])
    
    # Використовуємо HTML-розмітку, як зазначено у DefaultBotProperties
    await m.answer(
        "👋 Привіт! <b>@CryptoComboDaily</b>\nЯ надаю актуальні щоденні комбінації.\nНатисни кнопку нижче:", 
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
    )

# --- ВИПРАВЛЕНИЙ ХЕНДЛЕР ---
@dp.callback_query(F.data == "combo")
async def show_combo(c: types.CallbackQuery):
    # Крок 1: Обов'язково відповідаємо на CallbackQuery
    await c.answer("Оновлюю інформацію...")
    
    # Створення тексту для відображення
    text_to_display = (
        f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n"
        f"{combo_text}"
    )
    
    # Крок 2: Редагуємо повідомлення
    try:
        # Редагування повідомлення з актуальним комбо
        await c.message.edit_text(
            text_to_display, 
            parse_mode="HTML",
            # Додаємо назад кнопку, якщо вона була
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🎁 Отримати комбо", callback_data="combo")]
            ])
        )
    except TelegramAPIError as e:
        # Обробляємо помилку: Message is not modified
        if "message is not modified" in str(e):
            logging.info("Редагування пропущено: текст не змінився.")
            # Відповідь користувачу, що все ОК, але нічого не змінилося
            await c.answer("Комбо вже актуальне!", show_alert=False) 
        else:
            # Інші помилки API (наприклад, повідомлення занадто старе)
            logging.error(f"Помилка при редагуванні повідомлення: {e}")
            await c.answer("Помилка редагування. Спробуйте команду /start знову.", show_alert=True)


@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("Доступ заборонено!", show_alert=True)
        return
    
    # Відповідаємо на запит
    await c.answer() 
    
    await c.message.edit_text(
        f"<b>Адмінка</b>\nПоточний URL: <code>{source_url or 'НЕ ВСТАНОВЛЕНО'}</code>", 
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔄 Оновити зараз", callback_data="force")],
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start")] # Додаємо кнопку назад
        ])
    )
    
@dp.callback_query(F.data == "start")
async def back_to_start(c: types.CallbackQuery):
    # Повторне виконання логіки /start для кнопки "Назад"
    await c.answer()
    kb = [[types.InlineKeyboardButton(text="🎁 Отримати комбо", callback_data="combo")]]
    if c.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="🛠 Адмінка", callback_data="admin")])

    await c.message.edit_text(
        "👋 Привіт! <b>@CryptoComboDaily</b>\nЯ надаю актуальні щоденні комбінації.\nНатисни кнопку нижче:", 
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
    )


@dp.callback_query(F.data == "force")
async def force(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("Доступ заборонено!", show_alert=True)
        return
    
    await c.answer("Запускаю примусове оновлення...")
    await fetch()
    
    # Редагуємо повідомлення адмінки, щоб показати статус
    await c.message.edit_text("✅ Оновлено! Перевірте лог або запустіть /combo", 
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")]
        ])
    )

# Команди
@dp.message(F.text.startswith("/seturl"))
async def seturl(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    try:
        global source_url
        source_url = m.text.split(maxsplit=1)[1].strip()
        await m.answer(f"✅ URL збережено та встановлено як джерело:\n<code>{source_url}</code>")
        # Після встановлення URL, запускаємо перше оновлення
        await fetch() 
    except IndexError:
        await m.answer("Використання: <code>/seturl https://example.com/daily.txt</code>")

@dp.message(F.text.startswith("/setcombo"))
async def setcombo(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    global combo_text
    
    # Оновлення: перевіряємо, чи є текст після команди
    new_combo = m.text.partition(" ")[2].strip()
    
    if new_combo:
        combo_text = new_combo
        await m.answer("✅ Комбо збережено вручну.")
    else:
        await m.answer("Будь ласка, вкажіть текст комбо після команди. Наприклад: <code>/setcombo Карта А -> 1M</code>")

# Запуск
async def main():
    # Запускаємо планувальник як фонову задачу
    asyncio.create_task(scheduler()) 
    logging.info("БОТ ЗАПУЩЕНО")
    # Стартуємо обробку вхідних оновлень
    await dp.start_polling(bot) 

if __name__ == "__main__":
    # Перевірка наявності токена
    if not BOT_TOKEN:
        logging.error("Критична помилка: Змінна середовища BOT_TOKEN не встановлена.")
    elif ADMIN_ID == 0:
        logging.warning("Увага: Змінна середовища ADMIN_ID не встановлена або дорівнює 0.")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logging.info("Бот зупинено вручну.")
