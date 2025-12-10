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
            # Збільшуємо мінімальний розмір, щоб виключити банери/іконки
            if width and height and int(width) > 200 and int(height) > 200:
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
def parse_hamster(html: str, prefer_text: bool = False) -> dict:
    """
    Парсер Hamster. Повертає словник:
    - {'type': 'image', 'url': str}
    - {'type': 'text', 'cards': list[str], 'morse': str | None}
    - {'type': 'error', 'message': str}
    """
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["hamster"]

    # 1. Спроба знайти ЗОБРАЖЕННЯ (якщо prefer_text=False)
    if not prefer_text:
        image_url = _find_combo_image_url(soup, "hamster", base_url)
        if image_url:
            return {'type': 'image', 'url': image_url}

    # 2. ТЕКСТОВИЙ/МОРЗЕ FALLBACK
    morse_code = []
    cards = []
    
    # Регулярний вираз для пошуку шифру Морзе (буква + пробіл + крапки/тире)
    import re
    morse_pattern = re.compile(r'([a-zA-Z])\s*(\s*[\.\-]+)\s*$', re.IGNORECASE)
    
    header_found = False
    
    for tag in soup.find_all(["p", "li", "div", "span", "strong", "h1", "h2", "h3", "h4"]):
        text = tag.get_text(strip=True)
        
        # Заголовки допомагають знайти початок контенту
        if tag.name in ["h1", "h2", "h3", "h4"] and ("combo" in text.lower() or "cipher" in text.lower()):
            header_found = True
            continue # Пропускаємо сам заголовок
            
        # Якщо заголовок знайдено або це великий пост, починаємо парсинг
        if not header_found and tag.name not in ["h1", "h2", "h3", "h4"]:
             # Може бути просто текст у статті без явного заголовка
             pass 

        # Парсинг ШИФРУ МОРЗЕ
        morse_match = morse_pattern.search(text)
        if morse_match:
            letter = morse_match.group(1).upper()
            code = morse_match.group(2).strip().replace(' ', '')
            morse_code.append(f"{letter} {code}")
            
        # Парсинг КАРТОК (великі літери)
        if text.isupper() and 4 <= len(text) <= 30 and text not in cards and "combo" not in text.lower() and "cipher" not in text.lower():
            cards.append(text)
            
        # Обмежуємо кількість знайдених даних
        if len(cards) >= 3 and len(morse_code) >= 4:
            break
            
    if len(cards) >= 3 or len(morse_code) > 0:
        morse_string = "\n".join(morse_code) if morse_code else None
        return {'type': 'text', 'cards': cards[:3], 'morse': morse_string}
        
    return {'type': 'error', 'message': "⏳ <b>Комбо ще не опубліковане</b>"}

def parse_tapswap(html: str, prefer_text: bool = False) -> str:
    soup = BeautifulSoup(html, "html.parser")
    base_url = BASE_URLS["tapswap"]
    
    if not prefer_text:
        image_url = _find_combo_image_url(soup, "tapswap", base_url)
        if image_url:
            # Для TapSwap повертаємо рядок із префіксом
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

# ================== HANDLERS (ОНОВЛЕНО) ==================

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
        combo_result = None
        is_hamster = (game == "hamster")

        # 1. Спроба 1: Парсинг із зображенням
        # Для Hamster parser_func повертає словник, для інших - рядок
        if is_hamster:
            combo_data = parser_func(html, prefer_text=False)
            if combo_data['type'] == 'image':
                 combo_result = f"__IMAGE_URL__:{combo_data['url']}"
            elif combo_data['type'] == 'text':
                 # Зберігаємо текстові дані для фінальної обробки, якщо зображення не спрацює
                 combo_result = combo_data
            else:
                 combo_result = combo_data['message'] # Повідомлення про помилку/відсутність комбо
        else:
            # Для інших ігор, як і раніше, повертається рядок
            combo_result = parser_func(html, prefer_text=False)

        image_url = None
        
        # Обробка результату для Hamster (якщо був словник) або для інших (якщо був рядок з префіксом)
        if isinstance(combo_result, str) and combo_result.startswith("__IMAGE_URL__:") and len(combo_result) > 14:
            image_url = combo_result[14:]

        if image_url:
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
                    # Скидаємо image_url, щоб перейти до текстового парсингу
                    image_url = None 
                else:
                    # Інша невідома помилка Telegram, виводимо її користувачеві
                    raise e 
        
        # 2. Спроба 2: Парсинг лише тексту (якщо спроба зображення провалилася)
        
        # Якщо це Hamster, і ми вже маємо текстові дані (combo_data), використовуємо їх
        if is_hamster and isinstance(combo_result, dict) and combo_result['type'] == 'text':
            cards_text = "\n".join(f"• <b>{c}</b>" for c in combo_result['cards'])
            morse_text = (f"\n\n<b>Шифр Морзе:</b>\n{combo_result['morse']}" if combo_result['morse'] else "")
            
            text_body = f"{cards_text}{morse_text}"
        
        # Для інших ігор або якщо Hamster не знайшов ані зображення, ані повний текст з першої спроби, парсимо лише текст
        elif not image_url:
            # Парсимо лише текст, ігноруючи пошук зображень
            # Для Hamster, якщо ми тут, це означає, що combo_result був помилкою або не був встановлений належним чином
            if is_hamster:
                combo_data = parser_func(html, prefer_text=True)
                if combo_data['type'] == 'text':
                    cards_text = "\n".join(f"• <b>{c}</b>" for c in combo_data['cards'])
                    morse_text = (f"\n\n<b>Шифр Морзе:</b>\n{combo_data['morse']}" if combo_data['morse'] else "")
                    text_body = f"{cards_text}{morse_text}"
                else:
                    text_body = combo_data['message']
            else:
                # Для інших ігор: парсинг лише тексту
                text_body = parser_func(html, prefer_text=True)
                
        # Надіслати ТЕКСТ
        text = f"<b>{name}</b>\nКомбо на <b>{datetime.now():%d.%m.%Y}</b>\n\n{text_body}"
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
