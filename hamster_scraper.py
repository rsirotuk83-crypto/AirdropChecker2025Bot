import requests
from bs4 import BeautifulSoup
import logging
from typing import List
import re # Для більш гнучкого пошуку тексту

# --- КОНФІГУРАЦІЯ СТРУКТУРИ ---
# Цей скрепер налаштований спеціально для TON Station, 4 карти, джерело miningcombo.com

# ВАЖЛИВО: Новий URL для TON Station Combo
TARGET_URL = "https://miningcombo.com/ton-station/" 
EXPECTED_CARDS_COUNT = 4

# --- НАЛАШТУВАННЯ ЛОГУВАННЯ ТА ФАЙЛОВІ ОПЕРАЦІЇ ---
# (Логіка завантаження/збереження URL у файли тут відсутня, 
# оскільки вона має бути в bot.py, але ми використовуємо TARGET_URL)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - Scraper - %(message)s')

def load_combo_url() -> str:
    """Заглушка: У виробничому коді ця функція має бути в bot.py та завантажувати URL з persistence."""
    return TARGET_URL

def scrape_for_combo() -> List[str] | None:
    """
    Виконує синхронний скрапінг для отримання щоденного комбо TON Station.
    """
    url_to_scrape = load_combo_url() # Використовуємо наш новий URL
    
    try:
        logging.info(f"Починаю скрапінг TON Station на {url_to_scrape} для оновлення комбо ({EXPECTED_CARDS_COUNT} карт)...")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }

        response = requests.get(url_to_scrape, headers=headers, timeout=15)
        response.raise_for_status() # Викликає помилку для поганих статусів (4xx або 5xx)

        soup = BeautifulSoup(response.text, 'html.parser')

        # --- ЛОГІКА СЕЛЕКТОРІВ ДЛЯ miningcombo.com ---
        
        # 1. Шукаємо секцію, яка містить заголовок "TON Station Daily Combo"
        # Використовуємо регулярний вираз для гнучкості
        header_text_pattern = re.compile(r'ton station daily combo', re.IGNORECASE)
        
        # Шукаємо заголовок (h2, h3) з ключовими словами
        header = soup.find(['h2', 'h3'], string=header_text_pattern)
        
        combo_list_container = None
        if header:
            # Намагаємося знайти список (ul/ol) або блок (div), що йде безпосередньо за заголовком
            # Часто комбо розташовується у списку <ul> або безпосередньо у абзацах <p>
            combo_list_container = header.find_next_sibling(['ul', 'ol', 'div', 'p'])

        # Якщо не вдалося знайти за заголовком, спробуємо загальний пошук списку 
        # (часто на таких сайтах комбо виділено)
        if not combo_list_container:
            # Шукаємо перший список (ul) з елементами
            combo_list_container = soup.find('ul') 
            
        if not combo_list_container:
            logging.warning("Не вдалося знайти контейнер щоденного комбо TON Station.")
            return ["Скрапер: Секція не знайдена", "Перевірте HTML-селектори", f"Використовується URL: {url_to_scrape}"]

        # 2. Знаходимо елементи всередині контейнера
        # Шукаємо елементи списку (li) або абзаци (p) у контейнері
        combo_items = combo_list_container.find_all(['li', 'p', 'div'], limit=EXPECTED_CARDS_COUNT + 1) # +1 для запасу

        # 3. Витягуємо чистий текст та фільтруємо
        combo = [item.get_text(strip=True) for item in combo_items]
        combo = [c for c in combo if c] # Прибираємо порожні рядки

        if len(combo) < EXPECTED_CARDS_COUNT:
            logging.warning(f"Знайдено лише {len(combo)} елементів комбо (очікується {EXPECTED_CARDS_COUNT}).")
            return ["Скрапер: Неповне комбо", f"Знайдено менше {EXPECTED_CARDS_COUNT} елементів", "Спробуйте ручний /setcombo"]

        # 4. Обрізаємо до очікуваної кількості та повертаємо
        result = combo[:EXPECTED_CARDS_COUNT]
        logging.info(f"Скрапінг TON Station успішний. Нове комбо: {result}")
        return result

    except requests.exceptions.ConnectionError as e:
        logging.error(f"Помилка під час HTTP-запиту (ConnectionError): {e}")
        return [f"Помилка HTTP: ConnectionError", "Не вдалося підключитися", "Перевірте URL"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Помилка під час HTTP-запиту: {e}")
        return [f"Помилка HTTP: {e.__class__.__name__}", "Перевірте URL або змініть джерело", ""]
    except Exception as e:
        logging.error(f"Непередбачувана помилка під час скрапінгу: {e}")
        return [f"Непередбачувана помилка: {e.__class__.__name__}", "Зверніться до розробника", ""]

    return None

# --- ФОНОВИЙ ПЛАНУВАЛЬНИК ---

# Ця частина залишилася без змін, оскільки логіка таймера не змінюється
GLOBAL_COMBO_CARDS: List[str] = []
SCRAPING_INTERVAL_SECONDS = 3600 * 4 # Оновлення кожні 4 години

async def main_scheduler():
    """Фоновий планувальник для періодичного оновлення комбо."""
    global GLOBAL_COMBO_CARDS
    # Завантаження початкових карток з файлу (або імітація)
    # У цьому прикладі ми просто починаємо з порожнього списку.
    
    # Виконуємо скрапінг одразу при старті
    new_combo = scrape_for_combo()
    if new_combo and new_combo[0] not in ["Скрапер: Секція не знайдена", "Помилка HTTP: ConnectionError"]:
        GLOBAL_COMBO_CARDS = new_combo
    else:
        logging.warning(f"Початковий скрапінг провалився: {new_combo}. Спроба пізніше.")

    while True:
        await asyncio.sleep(SCRAPING_INTERVAL_SECONDS)
        
        new_combo = scrape_for_combo()
        if new_combo and new_combo[0] not in ["Скрапер: Секція не знайдена", "Помилка HTTP: ConnectionError"]:
            GLOBAL_COMBO_CARDS = new_combo
            logging.info(f"Планувальник: Успішно оновлено комбо на {GLOBAL_COMBO_CARDS}")
        else:
            logging.warning(f"Планувальник: Скрапінг провалився: {new_combo}")
