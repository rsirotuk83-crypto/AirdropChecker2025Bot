import os
import asyncio
import logging
import httpx
from datetime import datetime

from bs4 import BeautifulSoup
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# ================== CONFIG & LOGGING ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", 8080))

# --- КРИТИЧНА ПЕРЕВІРКА ЗМІННИХ ---
if not BOT_TOKEN or not WEBHOOK_HOST:
    # Важливо: використовуємо RuntimeError, щоб перервати запуск, якщо конфігурація неповна.
    raise RuntimeError(
        "❌ BOT_TOKEN або WEBHOOK_HOST не встановлено. Перевірте змінні середовища."
    )

# --- БЕЗПЕЧНИЙ WEBHOOK ШЛЯХ ---
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Використовуємо ParseMode.HTML для кращого форматування
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ================== SOURCES ==================
SOURCES = {
    "hamster": "https://hamster-combo.com",
    "tapswap": "https://miningcombo.com/tapswap-2/",
    "blum": "https://miningcombo.com/blum-2/",
    "cattea": "https://miningcombo.com/cattea/",
}

# ================== PARSERS (ТОЧКОВІ ВЕРСІЇ) ==================

def parse_hamster(html: str) -> str:
    """Парсить Hamster Kombat: шукає блок 'Today's Daily Combo' і елементи <li>."""
    soup = BeautifulSoup(html, "html.parser")

    # Шукаємо заголовок (h2, h3), що містить ключову фразу.
    header = soup.find(
        lambda tag: tag.name in ["h2", "h3"] and tag.get_text(strip=True) and "Today's Daily Combo" in tag.get_text(strip=True)
    )
    
    # Якщо заголовок не знайдено, комбо ще немає.
    if not header:
        return "⏳ <b>Комбо ще не опубліковане</b>"

    cards = []
    # Шукаємо елементи <li> в блоку після заголовка (це більш надійно).
    # У Hamster вони часто використовують <li>, а текст повністю великими літерами.
    for li in soup.select("li"):
        text = li.get_text(strip=True)
        # Евристика: 4 <= довжина <= 25 і всі літери великі
        if text.isupper() and 4 <= len(text) <= 25:
            cards.append(text)

    if len(cards) < 3:
        # Якщо знайшли заголовок, але мало карток, значить, оновлення не завершене.
        return "⏳ <b>Комбо ще не опубліковане</b>"

    return "\n".join(f"• <b>{c}</b>" for c in cards[:3])

def parse_tapswap(html: str) -> str:
    """Парсить TapSwap: шукає блок 'Video Code' і бере останнє слово (код)."""
    soup = BeautifulSoup(html, "html.parser")

    codes = []
    # Шукаємо <div>, який містить фразу "Video Code"
    for block in soup.find_all("div"):
        if "Video Code" in block.get_text(strip=True):
            # Розділяємо текст блоку і беремо останнє слово
            text_content = block.get_text(strip=True)
            code = text_content.split()[-1]
            
            # Валідація: код має бути літерно-цифровим
            if code.isalnum():
                codes.append(code)

    return "\n".join(f"• <b>{c}</b>" for c in codes[:5]) or "⏳ <b>Комбо ще не знайдено</b>"

def parse_blum(html: str) -> str:
    """Парсить Blum: шукає виділені жирним (<strong>) слова, що складаються з великих літер."""
    soup = BeautifulSoup(html, "html.parser")

    codes = []
    # На Blum коди часто виділяються через <strong>
    for strong in soup.find_all("strong"):
        c = strong.get_text(strip=True)
        # Евристика: великі літери та помірна довжина
        if c.isupper() and 4 < len(c) <= 20:
            codes.append(c)

    return "\n".join(f"• <b>{c}</b>" for c in codes[:5]) or "⏳ <b>Комбо ще не знайдено</b>"

def parse_cattea(html: str) -> str:
    """Парсить CatTea: шукає заголовок 'Cattea Daily Combo' і вміст після нього, відсікаючи меню."""
    soup = BeautifulSoup(html, "html.parser")

    # 1️⃣ Явний статус: комбо ще немає
    if "searching for today's cattea daily combo" in html.lower():
        return "⏳ <b>Комбо ще не знайдено</b>"

    # 2️⃣ Шукаємо блок із заголовком "Cattea Daily Combo"
    header = soup.find(
        lambda tag: tag.name in ["h2", "h3"]
        and tag.get_text(strip=True)
        and "cattea daily combo" in tag.get_text(strip=True).lower()
    )

    if not header:
        return "⏳ <b>Комбо ще не знайдено</b>"

    # 3️⃣ Беремо ТІЛЬКИ текст ПІСЛЯ цього заголовка
    combo_block = []
    # Обмежуємо пошук першими 10 елементами після заголовка
    for el in header.find_all_next(["p", "li", "strong"], limit=10):
        text = el.get_text(strip=True)
        if not text:
            continue

        # ❌ Відсікаємо навігаційні посилання/сміття
        if text.lower() in {"home", "about", "menu", "contact"}:
            continue

        # ✅ Нормальний combo-елемент (валідація довжини)
        if 3 <= len(text) <= 25:
            combo_block.append(text)

    return "\n".join(f"• <b>{c}</b>" for c in combo_block[:5]) or "⏳ <b>Комбо ще не знайдено</b>"


# ================== FETCH ==================
async def fetch(url: str) -> str:
    """Асинхронно отримує HTML-вміст за URL."""
    async with httpx.AsyncClient(timeout=20) as c:
        # Дозволяємо перенаправлення
        r = await c.get(url, follow_redirects=True) 
        # Викличе помилку, якщо статус коду >= 400
        r.raise_for_status() 
        return r.text


# ================== UI ==================
def main_kb():
    """Клавіатура головного меню."""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="🐹 Hamster", callback_data="hamster"),
            types.InlineKeyboardButton(text="⚡ TapSwap", callback_data="tapswap")
        ],
        [
            types.InlineKeyboardButton(text="🌸 Blum", callback_data="blum"),
            types.InlineKeyboardButton(text="🐱 CatTea", callback_data="cattea")
        ]
    ])
    
def back_kb():
    """Клавіатура для повернення в меню."""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="<< Назад до меню", callback_data="back_to_menu")]
    ])


# ================== HANDLERS ==================
@dp.message(CommandStart())
async def start(m: types.Message):
    """Обробка команди /start."""
    await m.answer(
        "<b>🎮 Щоденні комбо ігор</b>\n\nОбери гру:",
        reply_markup=main_kb()
    )


@dp.callback_query(F.data.in_(SOURCES.keys()))
async def send_combo(cb: types.CallbackQuery):
    """Обробляє запит комбо для обраної гри, використовуючи точкові парсери."""
    await cb.answer("Отримую дані...", cache_time=5)

    game = cb.data
    name = ""
    
    try:
        html = await fetch(SOURCES[game])

        # Використовуємо індивідуальні парсери
        if game == "hamster":
            combo = parse_hamster(html)
            name = "🐹 Hamster Kombat"
        elif game == "tapswap":
            combo = parse_tapswap(html)
            name = "⚡ TapSwap"
        elif game == "blum":
            combo = parse_blum(html)
            name = "🌸 Blum"
        else: # cattea
            combo = parse_cattea(html)
            name = "🐱 CatTea"

        text = (
            f"<b>{name}</b>\n"
            f"Комбо на <b>{datetime.now():%d.%m.%Y}</b>\n\n"
            f"{combo}"
        )

    except httpx.HTTPStatusError as e:
        log.error(f"HTTP Error for {game}: {e.response.status_code}")
        text = (
            f"❌ <b>Помилка доступу до джерела {game.upper()}!</b>\n"
            f"Сайт-джерело ({SOURCES[game]}) повернув помилку: {e.response.status_code}. "
            f"Спробуйте пізніше."
        )
    except httpx.RequestError as e:
        log.error(f"Request Error for {game}: {e}")
        text = (
            f"❌ <b>Помилка мережі при отриманні даних {game.upper()}!</b>\n"
            f"Не вдалося підключитися до сайту-джерела. "
            f"Перевірте з'єднання або спробуйте пізніше."
        )
    except Exception as e:
        log.error(f"General Error for {game}: {e}")
        text = (
            f"❌ <b>Виникла невідома помилка!</b>\n"
            f"Можливо, змінилась структура сайту-джерела. "
            f"Повідомте адміністратора: <code>{e}</code>"
        )


    try:
        # Редагуємо повідомлення та пропонуємо кнопку "Назад до меню"
        await cb.message.edit_text(text, reply_markup=back_kb())
    except Exception as e:
        log.warning(f"Failed to edit message: {e}")
        # Якщо редагування не вдалося, відправляємо нове повідомлення
        await cb.message.answer(text, reply_markup=back_kb())

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(cb: types.CallbackQuery):
    """Повертає користувача до головного меню."""
    await cb.answer()
    await cb.message.edit_text(
        "<b>🎮 Щоденні комбо ігор</b>\n\nОбери гру:",
        reply_markup=main_kb()
    )


# ================== WEBHOOK ==================
async def on_startup(app: web.Application):
    """Встановлює Webhook при старті."""
    try:
        await bot.delete_webhook(drop_pending_updates=True) 
        await bot.set_webhook(WEBHOOK_URL)
        log.info(f"✅ Webhook встановлено: {WEBHOOK_URL}")
    except Exception as e:
        log.critical(f"❌ КРИТИЧНА ПОМИЛКА: Не вдалося встановити Webhook: {e}")

# Ініціалізація aiohttp
app = web.Application()
app.on_startup.append(on_startup)

# SimpleRequestHandler реєструємо на захищеному шляху з токеном
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

if __name__ == "__main__":
    log.info(f"Запуск сервера на 0.0.0.0:{PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)
