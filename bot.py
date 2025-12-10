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
    raise RuntimeError(
        "❌ BOT_TOKEN або WEBHOOK_HOST не встановлено. Перевірте змінні середовища Railway."
    )

# --- БЕЗПЕЧНИЙ WEBHOOK ШЛЯХ (ВАЖЛИВО!) ---
# Використовуємо токен у шляху для безпеки
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Змінюємо ParseMode на HTML для кращої гнучкості форматування
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

# ================== PARSERS ==================
def parse_hamster(html: str) -> str:
    """Парсить Hamster Kombat: шукає <h3> або <strong> з текстом, що складається лише з великих літер."""
    soup = BeautifulSoup(html, "html.parser")

    cards = []
    # Шукаємо теги, які найчастіше використовуються для виділення карт
    for tag in soup.find_all(["h3", "strong", "p"]): 
        text = tag.get_text(strip=True)
        # Евристика: 4 < довжина < 25 і всі літери великі
        if text.isupper() and 4 < len(text) < 25:
            cards.append(text)

    if not cards:
        return "⏳ <b>Комбо ще не опубліковане</b> (або змінилась структура сайту)."

    return "\n".join(f"• <b>{c}</b>" for c in cards[:3])


def parse_codes_by_label(html: str) -> str:
    """
    Універсальний парсер для Blum/TapSwap (на miningcombo.com).
    УВАГА: Ця логіка дуже крихка, оскільки покладається на те, що код знаходиться 
    на наступному рядку після 'Code' або схожого слова.
    """
    soup = BeautifulSoup(html, "html.parser")
    lines = soup.get_text("\n").splitlines()

    codes = []
    label_keywords = ["Code", "Сode", "Комбо"]
    
    for i, line in enumerate(lines):
        # Перевіряємо, чи поточний рядок містить одне з ключових слів
        if any(kw in line for kw in label_keywords) and i + 1 < len(lines):
            # Беремо наступний рядок як потенційний код
            code = lines[i + 1].strip()
            
            # Валідація: код має бути коротким (2-15 символів) і складатися з літер/цифр
            if 2 <= len(code) <= 15 and code.isalnum():
                codes.append(code)

    if not codes:
        # Fallback: шукаємо <li> або <strong> з короткими, виділеними кодами
        for tag in soup.find_all(["li", "strong"]):
             text = tag.get_text(strip=True)
             if 2 <= len(text) <= 15 and text.isalnum() and text not in codes:
                 codes.append(text)

    return "\n".join(f"• <b>{c}</b>" for c in codes[:5]) or "⏳ <b>Комбо ще не знайдено</b>"


def parse_cattea(html: str) -> str:
    """Парсить CatTea: шукає list-items або попередження про відсутність комбо."""
    if "searching for today's" in html.lower():
        return "⏳ <b>CatTea ще не оновив комбо.</b>"

    soup = BeautifulSoup(html, "html.parser")
    codes = []

    # Шукаємо лише list items (<li>)
    for li in soup.find_all("li"):
        text = li.get_text(strip=True)
        # Валідація: 3 <= довжина <= 20 і складається з літер/цифр
        if 3 <= len(text) <= 20 and text.isalnum():
            codes.append(text)

    return "\n".join(f"• <b>{c}</b>" for c in codes[:5]) or "⏳ <b>Комбо не знайдено</b>"


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
    """Обробляє запит комбо для обраної гри."""
    await cb.answer("Отримую дані...", cache_time=5)

    game = cb.data
    name = ""
    
    try:
        html = await fetch(SOURCES[game])

        if game == "hamster":
            combo = parse_hamster(html)
            name = "🐹 Hamster Kombat"
        elif game == "tapswap":
            combo = parse_codes_by_label(html)
            name = "⚡ TapSwap"
        elif game == "blum":
            combo = parse_codes_by_label(html)
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
        # Обробка помилок 4xx/5xx (сайт недоступний)
        log.error(f"HTTP Error for {game}: {e.response.status_code}")
        text = (
            f"❌ <b>Помилка доступу до джерела {game.upper()}!</b>\n"
            f"Сайт-джерело ({SOURCES[game]}) повернув помилку: {e.response.status_code}. "
            f"Спробуйте пізніше."
        )
    except httpx.RequestError as e:
        # Обробка помилок мережі (Таймаут, DNS-помилки)
        log.error(f"Request Error for {game}: {e}")
        text = (
            f"❌ <b>Помилка мережі при отриманні даних {game.upper()}!</b>\n"
            f"Не вдалося підключитися до сайту-джерела. "
            f"Перевірте з'єднання або спробуйте пізніше."
        )
    except Exception as e:
        # Загальна помилка парсингу
        log.error(f"General Error for {game}: {e}")
        text = (
            f"❌ <b>Виникла невідома помилка!</b>\n"
            f"Можливо, змінилась структура сайту-джерела. "
            f"Повідомте адміністратора."
        )


    try:
        await cb.message.edit_text(text, reply_markup=back_kb())
    except Exception as e:
        # Уникаємо помилки, якщо текст не змінився, або сталася інша помилка Telegram
        log.warning(f"Failed to edit message: {e}")
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
        # Видаляємо старий webhook та оновлення
        await bot.delete_webhook(drop_pending_updates=True) 
        # Встановлюємо новий, захищений Webhook
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
