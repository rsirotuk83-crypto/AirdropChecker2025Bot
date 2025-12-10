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
    # Слова, які вказують на логотип чи іконку, і мають бути виключені
    EXCLUDED_KEYWORDS = ["logo", "icon", "favicon", "cropped", "74x95"] 
    
    # Спробуємо знайти зображення всередині основного контенту статті (типово для WordPress)
    content_area = soup.find(["article", "div"], class_=lambda x: x and ('entry-content' in x or 'main-content' in x or 'post-content' in x))
    if not content_area:
        content_area = soup # Fallback to searching the whole page

    for img in content_area.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "")
        title = img.get("title", "")
        
        # 1. Виключаємо зображення, які є логотипами або іконками
        img_check_string = src.lower() + alt.lower() + title.lower()
        if any(exc in img_check_string for exc in EXCLUDED_KEYWORDS):
            continue

        # 2. Зображення має бути релевантним АБО достатньо великим
        is_relevant = any(k in img_check_string for k in keywords)
        
        # Перевірка розміру: ігноруємо, якщо обидва розміри менше 100px (типова ознака логотипу)
        is_large_enough = False
        width = img.get("width")
        height = img.get("height")
        try:
            if width and height and int(width) > 100 and int(height) > 100:
                is_large_enough = True
        except ValueError:
            pass # Ігноруємо, якщо розміри не числові

        # Приймаємо, якщо воно релевантне АБО достатньо велике
        if is_relevant or is_large_enough:
            # Вирішення відносного шляху
            if src.startswith('http'):
                return src
            elif src.startswith('//'):
                return f"https:{src}"
            elif src.startswith('/'):
                return base_url.rstrip('/') + src
            
    return None

# ================== ПАРСЕРИ ==================

def parse_hamster(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["hamster"]

    # 1. Спроба знайти ЗОБРАЖЕННЯ
    image_url = _find_combo_image_url(soup, "hamster", base_url)
    if image_url:
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
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["tapswap"]
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

def parse_blum(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["blum"]
    image_url = _find_combo_image_url(soup, "blum", base_url)
    if image_url:
        return f"__IMAGE_URL__:{image_url}"
        
    codes = []
    for tag in soup.find_all(["strong", "p", "span", "div"]):
        text = tag.get_text(strip=True)
        if text.isupper() and 5 <= len(text) <= 20 and text not in codes:
            codes.append(text)
        if len(codes) >= 3:
            break
    return "\n".join(f"• <b>{c}</b>" for c in codes[:3]) or "⏳ <b>Комбо ще не знайдено</b>"

def parse_cattea(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["cattea"]
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
        return f"__IMAGE_URL__:{image_url}"

    # 2. ТЕКСТОВИЙ FALLBACK
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
    # Використовуємо cb.message.edit_text для індикації завантаження
    await cb.message.edit_text("⏳ Отримую дані...", reply_markup=main_kb()) 
    
    game = cb.data
    name = {
        "hamster": "🐹 Hamster Kombat",
        "tapswap": "⚡ TapSwap",
        "blum": "🌸 Blum",
        "cattea": "🐱 CatTea",
        "tonstation": "🚉 TON Station"
    }[game]

    try:
        html = await fetch(SOURCES[game])

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
            
            log.info(f"Sending image for {game} from URL: {image_url}") # Логування URL для діагностики

            # Надіслати ЗОБРАЖЕННЯ
            caption = f"<b>{name}</b>\nКомбо на <b>{datetime.now():%d.%m.%Y}</b>\n\n✅ <b>Комбо знайдено як зображення.</b>"
            
            # bot.send_photo автоматично видалить попередній індикатор
            await bot.send_photo(
                chat_id=cb.message.chat.id,
                photo=image_url,
                caption=caption,
                reply_markup=back_kb(),
                parse_mode=ParseMode.HTML
            )
            
            # Видалити старе текстове повідомлення-індикатор (якщо bot.send_photo його не видалив)
            try:
                # В ідеалі ми хочемо видалити лише те повідомлення, яке було "⏳ Отримую дані..."
                await cb.message.delete()
            except Exception as e:
                log.warning(f"Could not delete old message after sending photo: {e}")
                
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
