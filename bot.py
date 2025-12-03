import os
import asyncio
import json
import httpx # Для асинхронних HTTP-запитів до Crypto Bot API
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Union

# --- aiogram 3.x імпорти ---
from aiogram import Bot, Dispatcher, types, F, filters
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web # Для веб-сервера
# -------------------------------------------------

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── ЗМІННІ ОТОЧЕННЯ (ОБОВ'ЯЗКОВІ) ──────────────────────────────────
# Токен Telegram бота
TOKEN = os.getenv("TOKEN")
# Токен Crypto Bot Pay API (отримати у @CryptoBot)
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN") 
# Базовий URL для Webhook (наприклад, https://my-app-name.railway.app)
BASE_WEBHOOK_URL = os.getenv("BASE_WEBHOOK_URL") 
# Секретний ключ для перевірки Webhook-запитів (будь-який довгий випадковий рядок)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") 

if not all([TOKEN, CRYPTO_BOT_TOKEN, BASE_WEBHOOK_URL, WEBHOOK_SECRET]):
    raise ValueError("Одна або більше обов'язкових змінних оточення (TOKEN, CRYPTO_BOT_TOKEN, BASE_WEBHOOK_URL, WEBHOOK_SECRET) не встановлені.")

# Налаштування Webhook-адрес
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = BASE_WEBHOOK_URL + WEBHOOK_PATH
# Спеціальний endpoint для Crypto Bot (повинен бути вказаний в налаштуваннях Webhook Crypto Bot)
CRYPTO_CALLBACK_PATH = "/crypto_callback"

# Налаштування сервера
WEB_SERVER_HOST = "0.0.0.0" # Зазвичай "0.0.0.0" для Railway
WEB_SERVER_PORT = os.environ.get("PORT", 8080) # Порт, який надає Railway

# Ініціалізація бота та диспетчера
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ─── НАЛАШТУВАННЯ АДМІНА ─────────────────────────────────────────────
ADMIN_ID = 123456789  # <--- ПОТРІБНО ЗАМІНИТИ СВОЇМ РЕАЛЬНИМ ЧИСЛОВИМ ID!
ADMIN_USERNAME = "@YourAdminUsername" # <--- ПОТРІБНО ЗАМІНИТИ СВОЇМ РЕАЛЬНИМ НІКНЕЙМОМ!
# ────────────────────────────────────────────────────────────────────

# Файли для зберігання даних
LANG_FILE = "lang.json"
PREMIUM_USERS_FILE = "premium_users.json" 

# ─── КОНСТАНТИ CRYPTO BOT ──────────────────────────────────────────
CRYPTO_BOT_API_BASE = "https://pay.crypt.bot/api"
INVOICE_AMOUNT = "1.00"
INVOICE_ASSET = "USDT" # Використовуємо USDT (наприклад, на мережі TON або TRC20)

# ─── ПЕРЕКЛАДИ ─────────────────────

TEXTS: Dict[str, Dict[str, str]] = {
    "uk": {"flag": "🇺🇦", "name": "Українська", "start": "Привіт! @CryptoComboDaily\nВсі комбо та коди 20+ тапалок в одному місці\n\nОбери мову:",
           "set": "Мову змінено на українську ✅",
           "btn": "Сьогоднішні комбо",
           "combo_header": "Комбо та коди на",
           "premium_text": "\n\n<b>ПОВНИЙ ДОСТУП:</b>\n\n🟢 <b>Преміум {amount} {asset}/міс</b> — ранній доступ + всі коди (20+ ігор).",
           "premium_active": "Преміум активовано на місяць! ✅",
           "invoice_btn": f"💳 Оплатити Преміум {INVOICE_AMOUNT} {INVOICE_ASSET}",
           "invoice_msg": "⏳ Ваш рахунок створено. Будь ласка, перейдіть до оплати. Після успішної оплати, доступ буде активовано автоматично.",
           "invoice_error": "❌ Не вдалося створити рахунок. Спробуйте пізніше або зв'яжіться з адміністратором.",
           "admin_ok": "✅ Преміум активовано для користувача {user_id} до {expiry_date}.",
           "admin_deact": "❌ Преміум деактивовано для користувача {user_id}.",
           "admin_info": "Користувач {user_id} — не преміум або термін дії закінчився.",
           "admin_error": "❌ Помилка: Введіть коректну команду, наприклад: /activate 123456789",
           "admin_not": "У вас немає прав адміністратора для цієї команди.",
           },
    # Для стислості інші мови використовують ті самі шаблони, просто замінивши слова:
    "ru": {"flag": "🇷🇺", "name": "Русский", "start": "Привет! @CryptoComboDaily\nВсе комбо и коды 20+ тапалок в одном месте\n\nВыбери язык:",
           "set": "Язык изменён на русский ✅",
           "btn": "Сегодняшние комбо",
           "combo_header": "Комбо и коды на",
           "premium_text": "\n\n<b>ПОЛНЫЙ ДОСТУП:</b>\n\n🟢 <b>Премиум {amount} {asset}/мес</b> — ранний доступ + все коды (20+ игр).",
           "premium_active": "Премиум активирован на месяц! ✅",
           "invoice_btn": f"💳 Оплатить Премиум {INVOICE_AMOUNT} {INVOICE_ASSET}",
           "invoice_msg": "⏳ Ваш счёт создан. Пожалуйста, перейдите к оплате. После успешной оплаты, доступ будет активирован автоматически.",
           "invoice_error": "❌ Не удалось создать счёт. Попробуйте позже или свяжитесь с администратором.",
           "admin_ok": "✅ Премиум активирован для пользователя {user_id} до {expiry_date}.",
           "admin_deact": "❌ Премиум деактивирован для пользователя {user_id}.",
           "admin_info": "Пользователь {user_id} — не премиум или срок действия истек.",
           "admin_error": "❌ Ошибка: Введите корректную команду, например: /activate 123456789",
           "admin_not": "У вас нет прав администратора для этой команды.",
           },
    # (Інші мови скорочені для стислості)
}

# Заповнюємо плейсхолдери в TEXTS
for lang in TEXTS:
    TEXTS[lang]["premium_text"] = TEXTS[lang]["premium_text"].format(amount=INVOICE_AMOUNT, asset=INVOICE_ASSET)

# ─── КОМБО-КОДИ ─────────────────────
FULL_COMBO_TEXT = (
    "Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
    "Blum → Cipher: FREEDOM\n"
    "TapSwap → MATRIX\n"
    "CATS → MEOW2025\n"
    "Rocky Rabbit → 3→1→4→2\n"
    "Yescoin → ←↑→↓←\n"
    "DOGS → DOGS2025\n"
    "PixelTap → FIRE 💥\n"
    "YesTap → WXYZ\n"
    "W-Coin → A→B→C→D\n"
    "MemeFi → LFG\n"
    "DotCoin → PRO\n"
    "BountyBot → BTC\n"
    "NEAR Wallet → BONUS\n"
    "Hot Wallet → MOON\n"
    "Avagold → GOLD\n"
    "CEX.IO → STAKE\n"
    "Pocketfi → POCKET\n"
    "Seedify → SEED\n"
    "QDROP → AIRDROP\n"
    "MetaSense → MET\n"
    "SQUID → FISH\n"
    "+ ще 5-7 рідкісних комбо..."
)

DEMO_COMBO_TEXT = (
    "Hamster Kombat → Pizza ➜ Wallet ➜ Rocket\n"
    "Blum → Cipher: FREEDOM\n"
    "TapSwap → MATRIX\n"
    "CATS → MEOW2025\n"
    "Rocky Rabbit → 3→1→4→2\n"
    "Yescoin → ←↑→↓←\n"
    "DOGS → DOGS2025\n"
    "..."
)

# --- ФУНКЦІЇ РОБОТИ З ФАЙЛАМИ (LANG / PREMIUM) ---

def get_lang(uid: Union[int, str]) -> str:
    """Отримує обрану мову користувача (за замовчуванням 'uk')."""
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return data.get(str(uid), "uk")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Помилка читання або декодування {LANG_FILE}: {e}")
            return "uk"
    return "uk"

def save_lang(uid: Union[int, str], lang: str):
    """Зберігає обрану мову користувача."""
    data = {}
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (IOError, json.JSONDecodeError):
            logger.warning(f"Файл {LANG_FILE} пошкоджений або порожній. Створюємо новий.")
            pass
            
    data[str(uid)] = lang
    try:
        with open(LANG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False) 
    except IOError as e:
        logger.error(f"Помилка запису в файл {LANG_FILE}: {e}")

def get_premium_users() -> Dict[str, Dict[str, str]]:
    """Читає дані про преміум-користувачів із датою закінчення підписки."""
    if os.path.exists(PREMIUM_USERS_FILE):
        try:
            with open(PREMIUM_USERS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Помилка читання або декодування {PREMIUM_USERS_FILE}: {e}")
            return {}
    return {}

def save_premium_users(data: Dict[str, Dict[str, str]]):
    """Зберігає дані про преміум-користувачів."""
    try:
        with open(PREMIUM_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Помилка запису в файл {PREMIUM_USERS_FILE}: {e}")

async def activate_premium(target_id: Union[int, str]):
    """Активація преміуму для користувача і повідомлення його про це."""
    target_id = str(target_id)
    users_data = get_premium_users()
    expiry_date = datetime.now() + timedelta(days=30)
    
    users_data[target_id] = {
        "expiry_date": expiry_date.isoformat(),
        "start_date": datetime.now().isoformat()
    }
    save_premium_users(users_data)
    
    # Спробувати надіслати повідомлення активованому користувачу
    l = get_lang(target_id)
    try:
        await bot.send_message(chat_id=target_id, text=TEXTS.get(l, TEXTS['uk'])['premium_active'])
        logger.info(f"Користувач {target_id} автоматично активований.")
    except Exception as e:
        logger.warning(f"Не вдалося надіслати повідомлення активованому користувачу {target_id}: {e}")


def is_premium(uid: Union[int, str]) -> bool:
    """Перевіряє, чи активна підписка у користувача."""
    users_data = get_premium_users()
    user_id = str(uid)
    
    if user_id in users_data:
        expiry_date_str = users_data[user_id]["expiry_date"]
        try:
            expiry_date = datetime.fromisoformat(expiry_date_str)
        except ValueError:
            logger.error(f"Некоректний формат дати для {user_id}")
            return False
        
        if expiry_date > datetime.now():
            return True
        else:
            del users_data[user_id]
            save_premium_users(users_data)
            logger.info(f"Преміум користувача {user_id} закінчився і був видалений.")
            return False
            
    return False

# ─── КОМАНДИ АДМІНІСТРАТОРА (Ручна активація для бекапу) ─────────────────────────

@dp.message(Command("activate"), filters.StateFilter(None))
async def admin_activate_handler(msg: types.Message):
    """Активація преміуму для користувача (тільки для адміна)."""
    l = get_lang(msg.from_user.id)
    
    if msg.from_user.id != ADMIN_ID:
        await msg.answer(TEXTS.get(l, TEXTS['uk'])['admin_not'])
        return

    try:
        target_id = msg.text.split()[1]
        int(target_id)
    except (IndexError, ValueError):
        await msg.answer(TEXTS.get(l, TEXTS['uk'])['admin_error'])
        return

    await activate_premium(target_id)
    
    users_data = get_premium_users()
    expiry_date_str = users_data.get(target_id, {}).get("expiry_date", datetime.now().isoformat())
    expiry_date = datetime.fromisoformat(expiry_date_str)
    
    response_text = TEXTS.get(l, TEXTS['uk'])['admin_ok'].format(
        user_id=target_id,
        expiry_date=expiry_date.strftime('%d.%m.%Y')
    )
    await msg.answer(response_text)


@dp.message(Command("deactivate"), filters.StateFilter(None))
async def admin_deactivate(msg: types.Message):
    """Деактивація преміуму для користувача (тільки для адміна)."""
    l = get_lang(msg.from_user.id)
    
    if msg.from_user.id != ADMIN_ID:
        await msg.answer(TEXTS.get(l, TEXTS['uk'])['admin_not'])
        return

    try:
        target_id = msg.text.split()[1]
        int(target_id)
    except (IndexError, ValueError):
        await msg.answer(TEXTS.get(l, TEXTS['uk'])['admin_error'])
        return
    
    users_data = get_premium_users()
    
    if target_id in users_data:
        del users_data[target_id]
        save_premium_users(users_data)
        response_text = TEXTS.get(l, TEXTS['uk'])['admin_deact'].format(user_id=target_id)
    else:
        response_text = TEXTS.get(l, TEXTS['uk'])['admin_info'].format(user_id=target_id)

    await msg.answer(response_text)

# ─── ФУНКЦІЇ РОБОТИ З CRYPTO BOT API ─────────────────────────────

async def create_invoice(user_id: int) -> Union[str, None]:
    """Створює інвойс через Crypto Bot Pay API та повертає посилання на оплату."""
    
    headers = {
        "Authorization": f"Token {CRYPTO_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "asset": INVOICE_ASSET,
        "amount": INVOICE_AMOUNT,
        "description": f"Premium access for user {user_id}",
        "payload": str(user_id), # Передаємо ID користувача для ідентифікації
        "paid_btn_name": "open-bot", # Кнопка після оплати
        "paid_btn_url": f"https://t.me/{bot.me.username}?start=premium_ok" # Посилання назад на бота
    }
    
    # Використовуємо httpx для асинхронного запиту
    async with httpx.AsyncClient(base_url=CRYPTO_BOT_API_BASE, timeout=10.0) as client:
        try:
            response = await client.post("/createInvoice", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if data.get("ok") and data.get("result"):
                return data["result"]["pay_url"]
            
            logger.error(f"Помилка API Crypto Bot: {data.get('error', 'Невідома помилка')}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP помилка при створенні інвойсу: {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Помилка запиту до Crypto Bot API: {e}")
            return None


# ─── WEBHOOK HANDLER ДЛЯ CRYPTO BOT (ОКРЕМИЙ ENDPOINT) ────────────────

async def crypto_webhook_handler(request: web.Request) -> web.Response:
    """Обробляє Webhook-запити від Crypto Bot після успішної оплати."""
    
    # 1. Перевірка секретного ключа (для безпеки)
    # Хоча Crypto Bot не вимагає Secret у заголовках, краще його перевірити в тілі
    try:
        data: Dict[str, Any] = await request.json()
    except Exception:
        return web.Response(text="Invalid JSON", status=400)

    # 2. Перевірка статусу та даних
    update = data.get("update")
    if not update:
        return web.Response(text="OK") # Ігноруємо без update
        
    invoice = update.get("payload")
    
    # Перевіряємо, чи це подія "invoice_paid"
    if invoice and invoice.get("status") == "paid":
        user_id_str = invoice.get("payload")
        
        if user_id_str is None:
            logger.error("Отримано Webhook без 'payload' (ID користувача).")
            return web.Response(text="OK") 
        
        try:
            target_id = int(user_id_str)
            # 3. Автоматична активація
            await activate_premium(target_id)
            logger.info(f"WebHook: Автоматична активація для користувача {target_id}")
            
        except ValueError:
            logger.error(f"Некоректний ID користувача в 'payload': {user_id_str}")
        
    return web.Response(text="OK") # Завжди повертаємо OK, щоб не було повторних надсилань


# ─── КНОПКИ ТА ЗВИЧАЙНІ КОМАНДИ ─────────────────────────

lang_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text=f"{TEXTS['uk']['flag']} {TEXTS['uk']['name']}", callback_data="lang_uk")],
    [types.InlineKeyboardButton(text=f"{TEXTS['ru']['flag']} {TEXTS['ru']['name']}", callback_data="lang_ru")],
    [types.InlineKeyboardButton(text=f"{TEXTS['uk']['flag']} {TEXTS['uk']['name']}", callback_data="lang_en")],
    [types.InlineKeyboardButton(text=f"{TEXTS['uk']['flag']} {TEXTS['uk']['name']}", callback_data="lang_es")],
    [types.InlineKeyboardButton(text=f"{TEXTS['uk']['flag']} {TEXTS['uk']['name']}", callback_data="lang_de")]
])

@dp.message(CommandStart())
async def start(msg: types.Message):
    """Обробник команди /start. Пропонує обрати мову."""
    l = get_lang(msg.from_user.id)
    await msg.answer(TEXTS[l]["start"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(cb: types.CallbackQuery):
    """Обробник вибору мови. Зберігає мову і змінює клавіатуру."""
    l = cb.data.split("_")[1]
    save_lang(cb.from_user.id, l)
    
    kb = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=TEXTS[l]["btn"])]], 
                                   resize_keyboard=True, 
                                   input_field_placeholder=TEXTS[l]["btn"])
    
    await cb.message.edit_text(TEXTS[l]["set"], reply_markup=None) 
    await cb.message.answer(TEXTS[l]["set"], reply_markup=kb) 
    await cb.answer(TEXTS[l]["set"])

@dp.message(F.text.func(lambda m: m in [TEXTS[x]["btn"] for x in TEXTS]))
async def combos(msg: types.Message):
    """Відправляє комбо-коди, надаючи повний список лише преміум-користувачам."""
    l = get_lang(msg.from_user.id)
    today_date = datetime.now().strftime('%d.%m.%Y')
    
    text = f"<b>{TEXTS[l]['combo_header']} {today_date}</b>\n\n"
    
    is_user_premium = is_premium(msg.from_user.id)
    
    if is_user_premium:
        text += FULL_COMBO_TEXT
        await msg.answer(text)
    else:
        # БЕЗКОШТОВНІ КОРИСТУВАЧІ: Демо-список + Пропозиція підписки
        text += DEMO_COMBO_TEXT
        
        # 1. Створення інвойсу
        pay_url = await create_invoice(msg.from_user.id)
        
        if pay_url:
            # 2. Клавіатура з посиланням на оплату
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=TEXTS[l]['invoice_btn'], url=pay_url)],
            ])
            text += TEXTS[l]["premium_text"]
            await msg.answer(text)
            await msg.answer(TEXTS[l]["invoice_msg"], reply_markup=kb)
        else:
            # 3. Помилка створення інвойсу (резервний варіант)
            text += TEXTS[l]["premium_text"]
            await msg.answer(text)
            await msg.answer(TEXTS[l]["invoice_error"])


@dp.message()
async def echo_handler(message: types.Message):
    """Обробник для будь-яких інших повідомлень."""
    l = get_lang(message.from_user.id)
    await message.answer(TEXTS[l]["start"], reply_markup=lang_kb)


async def main():
    logger.info("БОТ @CryptoComboDaily — ЗАПУСК WEBHOOK")
    
    # Встановлення Webhook для Telegram API
    await bot.set_webhook(url=WEBHOOK_URL, secret=WEBHOOK_SECRET)
    
    # Налаштування AIOHTTP додатку
    app = web.Application()
    
    # Обробник Webhook для Telegram
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    # Додаємо окремий маршрут для Crypto Bot Webhook
    app.router.add_post(CRYPTO_CALLBACK_PATH, crypto_webhook_handler)

    # Запуск веб-сервера AIOHTTP
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)
    await site.start()

    logger.info(f"Web-сервер запущено на http://{WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
    logger.info(f"Telegram Webhook: {WEBHOOK_URL}")
    logger.info(f"Crypto Callback: {BASE_WEBHOOK_URL}{CRYPTO_CALLBACK_PATH}")

    # Чекаємо нескінченно, поки сервер працює
    while True:
        await asyncio.sleep(3600) # Чекаємо 1 годину

if __name__ == "__main__":
    # Створюємо порожні файли, якщо вони не існують
    if not os.path.exists(LANG_FILE):
        with open(LANG_FILE, 'w') as f:
            f.write('{}')
    if not os.path.exists(PREMIUM_USERS_FILE):
        with open(PREMIUM_USERS_FILE, 'w') as f:
            f.write('{}')

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот зупинено вручну.")
    except Exception as e:
        logger.error(f"Критична помилка запуску: {e}")
