import os
import logging
import asyncio
import json
import httpx
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "0")
ADMIN_ID = int(ADMIN_ID)

if not BOT_TOKEN or not CRYPTO_BOT_TOKEN or not ADMIN_ID:
    logging.error("ПОМИЛКА: Не встановлено BOT_TOKEN, CRYPTO_BOT_TOKEN або ADMIN_ID.")
    exit(1)

CRYPTO_BOT_API_URL = "https://pay.crypt.bot/api"

API_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Telegram-Bot-Api-Token": CRYPTO_BOT_TOKEN
}

DB_FILE = "db_state.json"
USER_SUBSCRIPTIONS: Dict[int, bool] = {}
IS_ACTIVE = False
COMBO_CONTENT = "❌ **Комбо ще не встановлено адміністратором.**"

AUTO_SOURCE_URL = ""  # Встав сюди URL для автооновлення, напр. "https://miningcombo.com/daily-combos"

load_persistent_state()

# ─── Запуск фонової задачі ──────────────────────
asyncio.create_task(combo_fetch_scheduler(bot))

# ─── Основний код бота ──────────────────────────
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()

# Хендлери
@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    welcome_message, keyboard = _build_start_message_content(
        message.from_user.first_name or "Користувач",
        user_id,
        is_admin
    )
    await message.answer(welcome_message, reply_markup=keyboard)

@dp.message(Command("combo"))
async def command_combo_handler(message: types.Message, bot: Bot) -> None:
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_ID
    is_premium = USER_SUBSCRIPTIONS.get(user_id, False)
   
    if is_admin or IS_ACTIVE or is_premium:
        date_str_raw = datetime.now().strftime('%d.%m.%Y')
        date_str_escaped = date_str_raw.replace('.', r'\.')
       
        combo_text_with_date = COMBO_CONTENT.format(date_str=date_str_escaped)
        final_combo_text = escape_all_except_formatting(combo_text_with_date)
       
        await bot.send_message(chat_id=message.chat.id, text=final_combo_text)
    else:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Отримати Premium 🔑", callback_data="get_premium")]
        ])
       
        premium_message_raw = r"""
🔒 **Увага\!** Щоб отримати актуальні комбо та коди, вам потрібна Premium\-підписка\.
Натисніть кнопку нижче, щоб оформити ранній доступ\.
"""
        premium_message = escape_all_except_formatting(premium_message_raw)
       
        await message.answer(
            premium_message,
            reply_markup=keyboard
        )

@dp.message(Command("admin_menu"))
async def admin_menu_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    text, keyboard = _build_admin_menu_content()
    await message.answer(text, reply_markup=keyboard)

@dp.message(Command("set_combo"))
async def command_set_combo(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    new_combo_text = message.text.replace('/set_combo', '', 1).strip()
   
    if not new_combo_text:
        await message.answer("⚠️ Використання: /set_combo {текст комбо тут}")
        return
       
    global COMBO_CONTENT
    COMBO_CONTENT = new_combo_text
    save_persistent_state()
    await message.answer("✅ Новий контент комбо встановлено!")
    await command_combo_handler(message, message.bot)

@dp.message(Command("set_source_url"))
async def command_set_source_url(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    new_url = message.text.replace('/set_source_url', '', 1).strip()
   
    if not new_url:
        await message.answer("⚠️ Використання: /set_source_url {url тут}")
        return
       
    global AUTO_SOURCE_URL
    AUTO_SOURCE_URL = new_url
    save_persistent_state()
    await message.answer("✅ URL для автооновлення встановлено!")
    await fetch_and_update_combo(message.bot)

@dp.callback_query()
async def inline_callback_handler(callback: types.CallbackQuery, bot: Bot):
    global IS_ACTIVE
    user_id = callback.from_user.id
   
    if user_id == ADMIN_ID:
        if callback.data == "back_to_start":
            welcome_message, keyboard = _build_start_message_content(
                callback.from_user.first_name or "Користувач",
                user_id,
                True
            )
            await callback.message.edit_text(welcome_message, reply_markup=keyboard)
            return
        
        elif callback.data == "activate_combo":
            IS_ACTIVE = True
            save_persistent_state()
            text, keyboard = _build_admin_menu_content()
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("Комбо активовано!")
            return
        
        elif callback.data == "deactivate_combo":
            IS_ACTIVE = False
            save_persistent_state()
            text, keyboard = _build_admin_menu_content()
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("Комбо деактивовано!")
            return
        
        elif callback.data == "run_auto_update":
            await callback.answer("Запускаю оновлення...")
            await fetch_and_update_combo(bot)
            text, keyboard = _build_admin_menu_content()
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
       
    if callback.data == "get_premium":
        await callback.answer("Переадресація на оплату...")
        # Код створення інвойсу (як у твоєму оригіналі)
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        invoice_data = await create_invoice_request(callback.from_user.id, bot_username)
       
        if invoice_data and invoice_data.get('ok') and invoice_data['result'].get('pay_url'):
            pay_url = invoice_data['result']['pay_url']
            invoice_id = invoice_data['result']['invoice_id']
           
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Сплатити (Crypto Bot) 💳", url=pay_url)],
                [types.InlineKeyboardButton(text="Я сплатив 💸", callback_data=f"check_payment_{invoice_id}")]
            ])
           
            await callback.message.edit_text(
                "💰 **Оплата Premium**\nДля отримання раннього доступу сплатіть 1 TON\nНатисніть 'Сплатити' і після — 'Я сплатив 💸'.",
                reply_markup=keyboard
            )
        else:
            await callback.message.answer("⚠️ Не вдалося створити платіжний інвойс. Спробуйте пізніше.")
       
    elif callback.data.startswith("check_payment_"):
        invoice_id = callback.data.split("_")[-1]
        await callback.answer("Перевіряю статус...")
       
        payment_info = await check_invoice_status(invoice_id)
       
        if payment_info and payment_info.get('ok'):
            status = payment_info['result']['status']
           
            if status == 'paid':
                USER_SUBSCRIPTIONS[user_id] = True
                save_persistent_state()
               
                await callback.message.edit_text("🎉 **Оплата успішна!** Ви отримали Premium-доступ.\nНадішліть /combo для актуальних кодів.")
                await callback.answer("Підписка активована!", show_alert=True)
                return
           
            elif status == 'pending':
                await callback.answer("Платіж ще обробляється. Спробуйте через хвилину.", show_alert=True)
                return
           
            elif status == 'expired':
                await callback.answer("Термін дії сплив. Створіть новий інвойс.", show_alert=True)
                await callback.message.edit_text("❌ Термін дії сплив. Натисніть, щоб створити новий:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="Створити новий інвойс 🔑", callback_data="get_premium")]
                ]))
                return
               
            else:
                await callback.answer(f"Статус платежу: {status}", show_alert=True)
       
        else:
            await callback.answer("Не вдалося отримати статус. Зверніться до адміністратора.", show_alert=True)

# ─── Запуск ─────────────────────────────
async def main():
    logging.info("Бот запущено. Починаю отримувати оновлення...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
