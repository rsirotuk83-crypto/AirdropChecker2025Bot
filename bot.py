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

if not BOT_TOKEN or not WEBHOOK_HOST:
    raise RuntimeError("BOT_TOKEN або WEBHOOK_HOST не встановлено")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Використовуємо parse_mode=ParseMode.HTML для коректного відображення жирного шрифту
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ================== SOURCES & BASE URLS ==================
SOURCES = {
    "hamster": "https://hamster-combo.com",
    "tapswap": "https://miningcombo.com/tapswap-2/",
    "blum": "https://miningcombo.com/blum-2/",
    "cattea": "https://miningcombo.com/cattea/",
    "tonstation": "https://miningcombo.com/ton-station/",
}

# Базові URL-адреси для коректного вирішення відносних шляхів зображень
BASE_URLS = {
    "hamster": "https://hamster-combo.com",
    "tapswap": "https://miningcombo.com",
    "blum": "https://miningcombo.com",
    "cattea": "https://miningcombo.com",
    "tonstation": "https://miningcombo.com",
}

# ================== ДОПОМІЖНА ФУНКЦІЯ ДЛЯ ЗОБРАЖЕНЬ ==================
def _find_combo_image_url(soup: BeautifulSoup, game_name: str, base_url: str) -> str | None:
    """Шукає тег <img> з ключовими словами та повертає абсолютний URL."""
    keywords = ["combo", "cipher", "комбо", game_name.lower()]
    
    for img in soup.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "")
        title = img.get("title", "")

        # Перевірка на ключові слова у відповідних атрибутах
        if any(k in src.lower() or k in alt.lower() or k in title.lower() for k in keywords):
            # Вирішення відносного шляху, якщо необхідно
            if src.startswith('http'):
                return src
            elif src.startswith('/'):
                # Додаємо базовий URL для відносних шляхів
                return base_url.rstrip('/') + src
            # Для інших випадків (наприклад, base64 або незрозумілих шляхів) ігноруємо
            
    return None

# ================== ПАРСЕРИ (ОНОВЛЕНО) ==================

def parse_hamster(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["hamster"]

    # 1. Спроба знайти ЗОБРАЖЕННЯ
    image_url = _find_combo_image_url(soup, "hamster", base_url)
    if image_url:
        # Спеціальний префікс, який сигналізує обробнику send_combo, що це URL зображення
        return f"__IMAGE_URL__:{image_url}"

    # 2. ТЕКСТОВИЙ FALLBACK (поточна логіка)
    header = soup.find(lambda tag: tag.name in ["h1", "h2", "h3", "h4"] and "combo" in tag.get_text(strip=True).lower())
    if not header:
        return "⏳ <b>Комбо ще не опубліковане</b>"
    cards = []
    for tag in header.find_all_next(["p", "li", "div", "span", "strong"]):
        text = tag.get_text(strip=True)
        if text.isupper() and 4 <= len(text) <= 30 and text not in cards:
            cards.append(text)
        if len(cards) >= 3:
            break
    if len(cards) < 3:
        return "⏳ <b>Комбо ще не опубліковане</b>"
    return "\n".join(f"• <b>{c}</b>" for c in cards[:3])

def parse_tapswap(html: str) -> str:
    # Залишаємо лише пошук тексту, оскільки TapSwap скоріш за все текстовий
    soup = BeautifulSoup(html, "html.parser")
    codes = []
    for tag in soup.find_all(["p", "div", "span", "strong"]):
        text = tag.get_text(strip=True)
        if "code" in text.lower() or "cipher" in text.lower():
            # Оновлена логіка: шукаємо 4-10 буквено-цифрових символів як код
            parts = text.split()
            for part in parts:
                cleaned_part = ''.join(filter(str.isalnum, part))
                if cleaned_part.isalnum() and 4 <= len(cleaned_part) <= 10:
                    codes.append(cleaned_part.upper())
    codes = list(dict.fromkeys(codes))
    return "\n".join(f"• <b>{c}</b>" for c in codes[:5]) or "⏳ <b>Комбо ще не знайдено</b>"

def parse_blum(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    codes = []
    for tag in soup.find_all(["strong", "p", "span", "div"]):
        text = tag.get_text(strip=True)
        # Blum завжди шукає великі літери
        if text.isupper() and 5 <= len(text) <= 20 and text not in codes:
            codes.append(text)
        if len(codes) >= 3:
            break
    return "\n".join(f"• <b>{c}</b>" for c in codes[:3]) or "⏳ <b>Комбо ще не знайдено</b>"

def parse_cattea(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if "searching" in html.lower() or "coming soon" in html.lower():
        return "⏳ <b>Комбо ще не знайдено (searching...)</b>"
    header = soup.find(lambda tag: tag.name in ["h2", "h3", "h4"] and "cattea" in tag.get_text(strip=True).lower())
    if not header:
        return "⏳ <b>Комбо ще не опубліковане</b>"
    cards = []
    for tag in header.find_all_next(["p", "li", "div", "strong", "span"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 3 and text not in cards:
            cards.append(text)
        if len(cards) >= 4:
            break
    return "\n".join(f"• <b>{c}</b>" for c in cards[:4]) or "⏳ <b>Комбо ще не знайдено</b>"

def parse_tonstation(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["tonstation"]

    # 1. Спроба знайти ЗОБРАЖЕННЯ
    image_url = _find_combo_image_url(soup, "ton station", base_url)
    if image_url:
        # Спеціальний префікс, який сигналізує обробнику send_combo, що це URL зображення
        return f"__IMAGE_URL__:{image_url}"

    # 2. ТЕКСТОВИЙ FALLBACK (поточна логіка)
    if "searching" in html.lower():
        return "⏳ <b>Комбо ще не знайдено (searching...)</b>"
    header = soup.find(lambda tag: tag.name in ["h2", "h3"] and "ton station" in tag.get_text(strip=True).lower())
    if not header:
        return "⏳ <b>Комбо ще не опубліковане</b>"
    cards = []
    for tag in header.find_all_next(["p", "li", "div"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 3 and text not in cards:
            cards.append(text)
        if len(cards) >= 4:
            break
    return "\n".join(f"• <b>{c}</b>" for c in cards[:4]) or "⏳ <b>Комбо ще не знайдено</b>"

# ================== FETCH ==================
async def fetch(url: str) -> str:
    async with httpx.AsyncClient(timeout=20) as c:
        log.info(f"HTTP Request: GET {url}")
        r = await c.get(url, follow_redirects=True)
        r.raise_for_status()
        return r.text

# ================== UI ==================
def main_kb():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="🐹 Hamster", callback_data="hamster"),
            types.InlineKeyboardButton(text="⚡ TapSwap", callback_data="tapswap")
        ],
        [
            types.InlineKeyboardButton(text="🌸 Blum", callback_data="blum"),
            types.InlineKeyboardButton(text="🐱 CatTea", callback_data="cattea")
        ],
        [types.InlineKeyboardButton(text="🚉 TON Station", callback_data="tonstation")]
    ])

def back_kb():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="<< Назад до меню", callback_data="back_to_menu")]
    ])

# ================== HANDLERS (ОНОВЛЕНО) ==================

@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer("<b>🎮 Щоденні комбо ігор</b>\n\nОбери гру:", reply_markup=main_kb())

@dp.callback_query(F.data.in_(SOURCES.keys()))
async def send_combo(cb: types.CallbackQuery):
    await cb.answer("Отримую дані...", cache_time=5)
    game = cb.data
    name = {
        "hamster": "🐹 Hamster Kombat",
        "tapswap": "⚡ TapSwap",
        "blum": "🌸 Blum",
        "cattea": "🐱 CatTea",
        "tonstation": "🚉 TON Station"
    }[game]

    try:
        # 1. Отримати HTML
        html = await fetch(SOURCES[game])

        # 2. Викликати відповідний парсер
        parser_map = {
            "hamster": parse_hamster,
            "tapswap": parse_tapswap,
            "blum": parse_blum,
            "cattea": parse_cattea,
            "tonstation": parse_tonstation,
        }
        combo_result = parser_map[game](html)

        # 3. Обробка результату: ЗОБРАЖЕННЯ чи ТЕКСТ
        if combo_result.startswith("__IMAGE_URL__:") and len(combo_result) > 14:
            image_url = combo_result[14:]
            
            # Надіслати ЗОБРАЖЕННЯ
            caption = f"<b>{name}</b>\nКомбо на <b>{datetime.now():%d.%m.%Y}</b>\n\n✅ <b>Комбо знайдено як зображення.</b>"
            await bot.send_photo(
                chat_id=cb.message.chat.id,
                photo=image_url,
                caption=caption,
                reply_markup=back_kb(),
                parse_mode=ParseMode.HTML
            )
            # Видалити старе повідомлення з кнопками, щоб уникнути дублювання
            await cb.message.delete()
        else:
            # Надіслати ТЕКСТ (стандартна логіка)
            text = f"<b>{name}</b>\nКомбо на <b>{datetime.now():%d.%m.%Y}</b>\n\n{combo_result}"
            await cb.message.edit_text(text, reply_markup=back_kb())

    except Exception as e:
        log.error(f"Error for {game}: {e}")
        text = f"❌ <b>Помилка для {name}</b>\nСпробуйте пізніше."
        try:
            await cb.message.edit_text(text, reply_markup=back_kb())
        except:
            await cb.message.answer(text, reply_markup=back_kb())

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(cb: types.CallbackQuery):
    await cb.answer()
    await cb.message.edit_text("<b>🎮 Щоденні комбо ігор</b>\n\nОбери гру:", reply_markup=main_kb())

# ================== WEBHOOK ==================
async def on_startup(app: web.Application):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    log.info(f"✅ Webhook встановлено: {WEBHOOK_URL}")

app = web.Application()
app.on_startup.append(on_startup)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

if __name__ == "__main__":
    log.info(f"Запуск сервера на 0.0.0.0:{PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)
