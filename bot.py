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
from aiogram.exceptions import TelegramBadRequest

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

BASE_URLS = {
    "hamster": "https://hamster-combo.com",
    "tapswap": "https://miningcombo.com",
    "blum": "https://miningcombo.com",
    "cattea": "https://miningcombo.com",
    "tonstation": "https://miningcombo.com",
}

# ================== ДОПОМІЖНА ФУНКЦІЯ ДЛЯ ЗОБРАЖЕНЬ (ОНОВЛЕНО) ==================
def _find_combo_image_url(soup: BeautifulSoup, game_name: str, base_url: str) -> str | None:
    """Шукає тег <img> з ключовими словами УСЕРЕДИНІ КОНТЕНТУ та повертає абсолютний URL."""
    
    # Ключові слова, які вказують на комбо
    keywords = ["combo", "cipher", "комбо", "daily", "щоденне", game_name.lower().replace(" ", "-")]
    # Слова, які вказують на логотип, іконку чи заглушку
    EXCLUDED_KEYWORDS = ["logo", "icon", "favicon", "cropped", "placeholder", "74x95", "150x150"] 
    
    content_area = soup.find(["article", "div"], class_=lambda x: x and ('entry-content' in x or 'main-content' in x or 'post-content' in x))
    if not content_area:
        content_area = soup

    for img in content_area.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "")
        title = img.get("title", "")
        
        img_check_string = src.lower() + alt.lower() + title.lower()
        
        # 1. Виключаємо зображення за ключовими словами
        if any(exc in img_check_string for exc in EXCLUDED_KEYWORDS):
            continue

        # 2. Зображення має бути релевантним АБО достатньо великим
        is_relevant = any(k in img_check_string for k in keywords)
        
        # Перевірка розміру (фільтр малих картинок)
        is_large_enough = False
        width = img.get("width")
        height = img.get("height")
        try:
            if width and height and int(width) > 100 and int(height) > 100:
                is_large_enough = True
        except ValueError:
            pass

        if is_relevant or is_large_enough:
            # Вирішення відносного шляху
            if src.startswith('http'):
                return src
            elif src.startswith('//'):
                return f"https:{src}"
            elif src.startswith('/'):
                return base_url.rstrip('/') + src
            
    return None

# ================== ПАРСЕРИ (З ДОДАТКОВИМ АРГУМЕНТОМ) ==================

# Тепер парсери приймають `prefer_text: bool`
def parse_hamster(html: str, prefer_text: bool = False) -> str:
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["hamster"]

    # 1. Спроба знайти ЗОБРАЖЕННЯ (якщо prefer_text=False)
    if not prefer_text:
        image_url = _find_combo_image_url(soup, "hamster", base_url)
        if image_url:
            return f"__IMAGE_URL__:{image_url}"

    # 2. ТЕКСТОВИЙ FALLBACK
    header = soup.find(lambda tag: tag.name in ["h1", "h2", "h3", "h4"] and "combo" in tag.get_text(strip=True).lower())
    if not header:
        return "⏳ <b>Комбо ще не опубліковане</b>"
    cards = []
    # Починаємо пошук тексту одразу після заголовка
    for tag in header.find_all_next(["p", "li", "div", "span", "strong"]):
        text = tag.get_text(strip=True)
        if text.isupper() and 4 <= len(text) <= 30 and text not in cards and "combo" not in text.lower():
            cards.append(text)
        if len(cards) >= 3:
            break
    if len(cards) < 3:
        return "⏳ <b>Комбо ще не опубліковане</b>"
    return "\n".join(f"• <b>{c}</b>" for c in cards[:3])

def parse_tapswap(html: str, prefer_text: bool = False) -> str:
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["tapswap"]
    
    if not prefer_text:
        image_url = _find_combo_image_url(soup, "tapswap", base_url)
        if image_url:
            return f"__IMAGE_URL__:{image_url}"
        
    codes = []
    for tag in soup.find_all(["p", "div", "span", "strong"]):
        text = tag.get_text(strip=True)
        if "code" in text.lower() or "cipher" in text.lower():
            parts = text.split()
            for part in parts:
                cleaned_part = ''.join(filter(str.isalnum, part))
                if cleaned_part.isalnum() and 4 <= len(cleaned_part) <= 10:
                    codes.append(cleaned_part.upper())
    codes = list(dict.fromkeys(codes))
    return "\n".join(f"• <b>{c}</b>" for c in codes[:5]) or "⏳ <b>Комбо ще не знайдено</b>"

def parse_blum(html: str, prefer_text: bool = False) -> str:
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["blum"]
    
    if not prefer_text:
        image_url = _find_combo_image_url(soup, "blum", base_url)
        if image_url:
            return f"__IMAGE_URL__:{image_url}"
        
    codes = []
    for tag in soup.find_all(["strong", "p", "span", "div"]):
        text = tag.get_text(strip=True)
        if text.isupper() and 5 <= len(text) <= 20 and text not in codes and "combo" not in text.lower():
            codes.append(text)
        if len(codes) >= 3:
            break
    return "\n".join(f"• <b>{c}</b>" for c in codes[:3]) or "⏳ <b>Комбо ще не знайдено</b>"

def parse_cattea(html: str, prefer_text: bool = False) -> str:
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["cattea"]
    
    if not prefer_text:
        image_url = _find_combo_image_url(soup, "cattea", base_url)
        if image_url:
            return f"__IMAGE_URL__:{image_url}"
        
    if "searching" in html.lower() or "coming soon" in html.lower():
        return "⏳ <b>Комбо ще не знайдено (searching...)</b>"
    
    header = soup.find(lambda tag: tag.name in ["h2", "h3", "h4"] and "cattea" in tag.get_text(strip=True).lower())
    if not header:
        return "⏳ <b>Комбо ще не опубліковане</b>"
    cards = []
    for tag in header.find_all_next(["p", "li", "div", "strong", "span"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 3 and text not in cards and "combo" not in text.lower():
            cards.append(text)
        if len(cards) >= 4:
            break
    return "\n".join(f"• <b>{c}</b>" for c in cards[:4]) or "⏳ <b>Комбо ще не знайдено</b>"

def parse_tonstation(html: str, prefer_text: bool = False) -> str:
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["tonstation"]

    if not prefer_text:
        image_url = _find_combo_image_url(soup, "ton station", base_url)
        if image_url:
            return f"__IMAGE_URL__:{image_url}"

    if "searching" in html.lower():
        return "⏳ <b>Комбо ще не знайдено (searching...)</b>"
    
    header = soup.find(lambda tag: tag.name in ["h2", "h3"] and "ton station" in tag.get_text(strip=True).lower())
    if not header:
        return "⏳ <b>Комбо ще не опубліковане</b>"
    cards = []
    for tag in header.find_all_next(["p", "li", "div"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 3 and text not in cards and "combo" not in text.lower():
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

# ================== HANDLERS (КЛЮЧОВЕ ОНОВЛЕННЯ) ==================

@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer("<b>🎮 Щоденні комбо ігор</b>\n\nОбери гру:", reply_markup=main_kb())

@dp.callback_query(F.data.in_(SOURCES.keys()))
async def send_combo(cb: types.CallbackQuery):
    # Початковий індикатор
    await cb.message.edit_text("⏳ Отримую дані...", reply_markup=main_kb()) 
    
    game = cb.data
    name = {
        "hamster": "🐹 Hamster Kombat",
        "tapswap": "⚡ TapSwap",
        "blum": "🌸 Blum",
        "cattea": "🐱 CatTea",
        "tonstation": "🚉 TON Station"
    }[game]

    # Визначаємо функцію парсера
    parser_map = {
        "hamster": parse_hamster,
        "tapswap": parse_tapswap,
        "blum": parse_blum,
        "cattea": parse_cattea,
        "tonstation": parse_tonstation,
    }
    parser_func = parser_map[game]
    
    try:
        html = await fetch(SOURCES[game])

        # Спроба 1: Парсинг із зображенням
        combo_result = parser_func(html, prefer_text=False)
        is_image_attempt = False
        
        if combo_result.startswith("__IMAGE_URL__:") and len(combo_result) > 14:
            image_url = combo_result[14:]
            is_image_attempt = True
            
            log.info(f"Attempting to send image for {game} from URL: {image_url}")

            # Надіслати ЗОБРАЖЕННЯ
            caption = f"<b>{name}</b>\nКомбо на <b>{datetime.now():%d.%m.%Y}</b>\n\n✅ <b>Комбо знайдено як зображення.</b>"
            
            try:
                await bot.send_photo(
                    chat_id=cb.message.chat.id,
                    photo=image_url,
                    caption=caption,
                    reply_markup=back_kb(),
                    parse_mode=ParseMode.HTML
                )
                # Якщо успішно, видаляємо старий індикатор
                await cb.message.delete()
                return # Успіх, виходимо
                
            except TelegramBadRequest as e:
                # Обробка помилок завантаження зображень (failed to get HTTP URL content, wrong type)
                if "failed to get HTTP URL content" in str(e) or "wrong type of the web page content" in str(e):
                    log.warning(f"Image send failed for {game} ({image_url}). Reason: {e}. Falling back to text.")
                    # Скидаємо прапор is_image_attempt, щоб перейти до текстового парсингу
                    is_image_attempt = False
                    
                else:
                    # Інша невідома помилка Telegram, виводимо її користувачеві
                    raise e 
        
        # Спроба 2: Парсинг лише тексту, якщо спроба зображення провалилася або не було знайдено зображення
        if not is_image_attempt:
            # Парсимо лише текст, ігноруючи пошук зображень
            combo_result = parser_func(html, prefer_text=True)
            text = f"<b>{name}</b>\nКомбо на <b>{datetime.now():%d.%m.%Y}</b>\n\n{combo_result}"
            await cb.message.edit_text(text, reply_markup=back_kb())


    except Exception as e:
        log.error(f"Critical Error for {game}: {e}")
        text = f"❌ <b>Критична помилка для {name}</b>\nСпробуйте пізніше. Деталі: {type(e).__name__}"
        try:
            await cb.message.edit_text(text, reply_markup=back_kb())
        except:
            await cb.message.answer(text, reply_markup=back_kb())

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(cb: types.CallbackQuery):
    await cb.answer()
    menu_text = "<b>🎮 Щоденні комбо ігор</b>\n\nОбери гру:"
    try:
        # 1. Спроба відредагувати повідомлення (працює для текстових повідомлень)
        await cb.message.edit_text(menu_text, reply_markup=main_kb())
    except Exception as e:
        log.warning(f"Failed to edit message back to menu: {e}. Sending new message instead.")
        # 2. Якщо не вдалося відредагувати (наприклад, це було фото), надсилаємо нове повідомлення
        await cb.message.answer(menu_text, reply_markup=main_kb())
        try:
             # 3. Видаляємо повідомлення, до якого була прикріплена кнопка "Назад" (тобто фото)
             await cb.message.delete()
        except Exception as e:
             log.warning(f"Failed to delete old photo message: {e}")


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
