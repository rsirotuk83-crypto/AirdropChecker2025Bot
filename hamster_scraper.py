import requests
from bs4 import BeautifulSoup
import logging
from typing import List

# --- ОНОВЛЕНИЙ TARGET_URL ---
# Використовуємо відомий і надійний сторонній ресурс, який регулярно публікує комбо.
# ВАЖЛИВО: Якщо цей URL перестане працювати, вам потрібно буде знайти новий
# надійний сайт і оновити URL та селектори нижче.
TARGET_URL = "https://example-crypto-news.com/hamster-kombat-daily-combo" 
# Я вставив приклад. Якщо ви знаєте краще джерело, замініть його.
# Наприклад: "https://cryptorank.io/news/hamster-kombat-combo-today" (реальний приклад)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - Scraper - %(message)s')

def scrape_for_combo() -> List[str] | None:
    """
    Виконує синхронний скрапінг для отримання щоденного комбо.
    Використовує більш гнучкі селектори, припускаючи, що комбо
    перераховане у вигляді списку або окремих абзаців у статті.
    """
    try:
        logging.info(f"Починаю скрапінг на {TARGET_URL} для оновлення комбо...")

        # Використовуємо User-Agent для імітації браузера
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }

        response = requests.get(TARGET_URL, headers=headers, timeout=15)
        response.raise_for_status() # Викликає помилку для поганих статусів (4xx або 5xx)

        soup = BeautifulSoup(response.text, 'html.parser')

        # --- КРИТИЧНА ЛОГІКА СЕЛЕКТОРІВ (ОНОВЛЕНО) ---
        
        # 1. Спробуємо знайти контейнер, який, імовірно, містить лише комбо.
        # Шукаємо блок, який містить заголовок "Daily Combo" або "Щоденне комбо"
        combo_keywords = ['combo', 'daily', 'cards', 'щоденне']
        
        # Намагаємося знайти список (ul/ol) або блок (div) за атрибутами,
        # які можуть містити ключові слова. Це більш надійно, ніж вигаданий клас.
        combo_list_container = soup.find('ul', class_=lambda c: c and any(k in c.lower() for k in combo_keywords))
        
        if not combo_list_container:
            combo_list_container = soup.find('ol', class_=lambda c: c and any(k in c.lower() for k in combo_keywords))
        
        # Якщо контейнер не знайдено, пробуємо знайти його за загальною структурою статті
        if not combo_list_container:
            # Шукаємо блок тексту, який містить заголовок H3/H2 з ключовим словом "combo"
            header = soup.find(['h2', 'h3'], string=lambda t: t and any(k in t.lower() for k in combo_keywords))
            if header:
                # Беремо наступний елемент, який, можливо, є списком
                combo_list_container = header.find_next_sibling(['ul', 'ol', 'div', 'p'])

        if not combo_list_container:
            logging.warning("Не вдалося знайти блок щоденного комбо за новими селекторами.")
            return ["Скрапер: Секція не знайдена", "Перевірте HTML-селектори", f"Використовується URL: {TARGET_URL}"]

        # 2. Знаходимо три елементи всередині контейнера
        # Шукаємо елементи списку або абзаци в контейнері
        combo_items = combo_list_container.find_all(['li', 'p', 'div'], limit=3)

        if len(combo_items) < 3:
            logging.warning(f"Знайдено лише {len(combo_items)} елементів комбо (очікується 3).")
            return ["Скрапер: Неповне комбо", "Знайдено менше 3 елементів", "Перевірте сайт"]

        # 3. Витягуємо чистий текст з кожного елемента
        combo = [item.get_text(strip=True) for item in combo_items]
        
        # 4. Фільтруємо порожні рядки
        combo = [c for c in combo if c]

        if combo and len(combo) >= 3:
            logging.info(f"Скрапінг успішний. Нове комбо: {combo[:3]}")
            return combo[:3] # Повертаємо перші три елементи

    except requests.exceptions.RequestException as e:
        logging.error(f"Помилка під час HTTP-запиту: {e}")
        return [f"Помилка HTTP: {e.__class__.__name__}", "Не вдалося підключитися", "Перевірте URL"]
    except Exception as e:
        logging.error(f"Непередбачувана помилка під час скрапінгу: {e}")
        return [f"Непередбачувана помилка: {e.__class__.__name__}", "Зверніться до розробника", ""]

    return None
