import os
import asyncio
import logging
import httpx
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

# === Налаштування ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не встановлено!")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === Supabase ===
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# === Глобальні змінні ===
GLOBAL_COMBO_ACTIVATION_STATUS = True
PREMIUM_USERS = {}
COMBO_URL = None
combo_text = "Комбо ще не встановлено"

# === Функції Supabase ===
async def supabase_fetch(table: str):
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers)
        return r.json() if r.status_code == 200 else []

async def supabase_upsert(table: str, data: dict):
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    async with httpx.AsyncClient() as client:
        await client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)

# === Завантаження стану при старті ===
async def load_state():
    global GLOBAL_COMBO_ACTIVATION_STATUS, PREMIUM_USERS, COMBO_URL, combo_text
    try:
        config = await supabase_fetch("config")
        if config:
            cfg = config[0]
            GLOBAL_COMBO_ACTIVATION_STATUS = cfg.get("global_active", True)
            COMBO_URL = cfg.get("combo_url")
        users = await supabase_fetch("premium_users")
        PREMIUM_USERS = {int(u["user_id"]): u["expires_at"] for u in users if u.get("expires_at")}
        if COMBO_URL:
            await fetch_combo()
    except Exception as e:
        logging.error(f"Помилка завантаження з Supabase: {e}")

# === Збереження стану ===
async def save_state():
    await supabase_upsert("config", [{
        "id": 1,
        "global_active": GLOBAL_COMBO_ACTIVATION_STATUS,
        "combo_url": COMBO_URL
    }])

# === Оновлення комбо ===
async def fetch_combo():
    global combo_text
    if not COMBO_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(COMBO_URL)
            if r.status_code == 200:
                combo_text = r.text.strip()
    except Exception as e:
        logging.error(f"Помилка завантаження комбо: {e}")

# === Перевірки ===
def is_admin(user_id):
    return user_id == ADMIN_ID

def is_premium(user_id):
    if is_admin(user_id):
        return True
    expiry = PREMIUM_USERS.get(user_id)
    if expiry:
        return datetime.now(timezone.utc) < datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    return False

# === Хендлери ===
@dp.message(CommandStart())
async def start(m: types.Message):
    kb = [[types.InlineKeyboardButton(text="Отримати комбо", callback_data="get_combo")]]
    if is_admin(m.from_user.id):
        kb.append([types.InlineKeyboardButton(text="Адмінка", callback_data="admin_menu")])
    await m.answer("Привіт! @CryptoComboDaily\nНатисни кнопку:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "get_combo")
async def get_combo(c: types.CallbackQuery):
    if is_premium(c.from_user.id) or GLOBAL_COMBO_ACTIVATION_STATUS:
        await c.message.edit_text(f"<b>Комбо на {datetime.now():%d.%m.%Y}</b>\n\n{combo_text}", parse_mode="HTML")
    else:
        await c.answer("Доступно лише преміум або при глобальній активації", show_alert=True)

@dp.callback_query(F.data == "admin_menu")
async def admin_menu(c: types.CallbackQuery):
    if not is_admin(c.from_user.id): return
    status = "АКТИВНО" if GLOBAL_COMBO_ACTIVATION_STATUS else "НЕАКТИВНО"
    kb = [
        [types.InlineKeyboardButton(text=f"Глобально: {status}", callback_data="toggle_global")],
        [types.InlineKeyboardButton(text="Оновити комбо", callback_data="force_update")],
        [types.InlineKeyboardButton(text="Встановити URL", callback_data="set_url")]
    ]
    await c.message.edit_text("Адмін-панель", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.in_({"toggle_global", "force_update", "set_url"}))
async def admin_actions(c: types.CallbackQuery):
    if not is_admin(c.from_user.id): return
    if c.data == "toggle_global":
        global GLOBAL_COMBO_ACTIVATION_STATUS
        GLOBAL_COMBO_ACTIVATION_STATUS = not GLOBAL_COMBO_ACTIVATION_STATUS
        await save_state()
        await c.answer(f"Глобально {'увімкнено' if GLOBAL_COMBO_ACTIVATION_STATUS else 'вимкнено'}")
    elif c.data == "force_update":
        await fetch_combo()
        await c.answer("Оновлено!")
    elif c.data == "set_url":
        await c.message.edit_text("Надішли новий URL для комбо:")
        dp["waiting_url"] = c.from_user.id

@dp.message(F.text.startswith(("http://", "https://")))
async def handle_url(m: types.Message):
    if dp.get("waiting_url") == m.from_user.id and is_admin(m.from_user.id):
        global COMBO_URL
        COMBO_URL = m.text.strip()
        await save_state()
        await fetch_combo()
        await m.answer(f"URL збережено та комбо оновлено:\n{COMBO_URL}")
        dp["waiting_url"] = None

# === Запуск ===
async def main():
    await load_state()
    await fetch_combo()  # перший запуск
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

async def scheduler():
    while True:
        await asyncio.sleep(24 * 3600)
        await fetch_combo()

if __name__ == "__main__":
    asyncio.run(main())
