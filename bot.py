import os
import asyncio
import logging
import httpx
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

combo_text = "Комбо ще не встановлено"
source_url = ""

async def fetch():
    global combo_text
    if not source_url: return
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(source_url)
            if r.status_code == 200:
                new = r.text.strip()
                if new and new != combo_text:
                    combo_text = new
                    if ADMIN_ID:
                        await bot.send_message(ADMIN_ID, "Комбо оновлено!")
    except Exception as e:
        if ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"Помилка: {e}")

async def scheduler():
    await asyncio.sleep(30)
    while True:
        await fetch()
        await asyncio.sleep(24 * 3600)

@dp.message(CommandStart())
async def start(m: types.Message):
    kb = [[types.InlineKeyboardButton(text="Отримати комбо", callback_data="getcombo")]]
    if m.from_user.id == ADMIN_ID:
        kb.append([types.InlineKeyboardButton(text="Адмінка", callback_data="admin")])
    await m.answer("Привіт! @CryptoComboDaily\nНатисни кнопку:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

# ЦЕЙ ХЕНДЛЕР ПРАЦЮЄ — callback_data збігається з кнопкою
@dp.callback_query(F.data == "getcombo")
async def show_combo(c: types.CallbackQuery):
    await c.message.edit_text(f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo_text}", parse_mode="HTML")

@dp.callback_query(F.data == "admin")
async def admin_panel(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    await c.message.edit_text("Адмінка", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Оновити зараз", callback_data="force")]
    ]))

@dp.callback_query(F.data == "force")
async def force(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    await fetch()
    await c.answer("Оновлено!")

@dp.message(F.text.startswith("/seturl"))
async def seturl(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    try:
        global source_url
        source_url = m.text.split(maxsplit=1)[1]
        await m.answer(f"URL збережено:\n{source_url}")
        await fetch()
    except:
        await m.answer("Використання: /seturl https://...")

@dp.message(F.text.startswith("/setcombo"))
async def setcombo(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    global combo_text
    combo_text = m.text.partition(" ")[2] or "Порожнє"
    await m.answer("Комбо збережено")

async def main():
    asyncio.create_task(scheduler())
    logging.info("БОТ ЗАПУЩЕНО — КНОПКИ ПРАЦЮЮТЬ")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
