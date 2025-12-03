# Файл: /app/bot.py

import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- 1. Налаштування ---

# УВАГА: Замініть 'YOUR_BOT_TOKEN' на ваш реальний токен!
API_TOKEN = 'YOUR_BOT_TOKEN'

# Налаштування логування для виведення інформації про роботу бота
logging.basicConfig(level=logging.INFO)

# Ініціалізація бота та диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- 2. Функції Клавіатур ---

def get_language_markup():
    """Створює клавіатуру для вибору мови.
    
    Це місце, де виправлено помилку: 
    використовуємо 'text=' для передачі тексту кнопки.
    """
    markup = InlineKeyboardMarkup(row_width=1)
    
    # ВИПРАВЛЕНО РЯДОК З ПОМИЛКОЮ (Аналог рядка 60 у вашому лозі)
    # types.InlineKeyboardButton("Українська", callback_data="lang_uk")  <-- Помилка була тут
    
    ukraine_button = InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_uk") 
    english_button = InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en") 
    
    markup.add(ukraine_button, english_button)
    return markup

# --- 3. Обробники Команд та Повідомлень ---

@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    """Обробник команди /start. Відправляє привітання та пропонує обрати мову."""
    
    await message.reply(
        "Привіт! Я AirdropChecker2025Bot. Будь ласка, оберіть вашу мову:",
        reply_markup=get_language_markup()
    )

@dp.callback_query_handler(text_startswith="lang_")
async def process_language_selection(call: types.CallbackQuery):
    """Обробник натискання кнопок вибору мови."""
    
    # Вилучаємо обрану мову з callback_data (наприклад, "uk" або "en")
    language_code = call.data.split('_')[1]
    
    if language_code == 'uk':
        response_text = "🎉 Мова успішно змінена на **Українську**! Ласкаво просимо!"
    elif language_code == 'en':
        response_text = "🎉 Language successfully changed to **English**! Welcome!"
    else:
        response_text = "Невідома мова."

    # Надсилаємо відповідь користувачеві
    await call.message.edit_text(response_text, parse_mode=types.ParseMode.MARKDOWN)
    
    # Відповідаємо на запит CallBack, щоб прибрати "годинник" з кнопки
    await call.answer(f"Обрано: {language_code.upper()}")


# --- 4. Запуск Бота ---

if __name__ == '__main__':
    # Запускаємо бота в режимі опитування (polling)
    executor.start_polling(dp, skip_updates=True)
