import requests
from bs4 import BeautifulSoup
import logging
from typing import List

# URL, який будемо скрапити.
# Використовуйте найбільш надійне джерело, наприклад, прямий лінк на сторінку з комбо.
TARGET_URL = "https://hamsterkombat.io/"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - Scraper - %(message)s')

def scrape_for_combo() -> List[str] | None:
    """
    Виконує синхронний скрапінг для отримання щоденного комбо.
    Ця функція повинна бути запущена через asyncio.to_thread() у bot.py.
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

        # --- КРИТИЧНА ЛОГІКА СЕЛЕКТОРІВ ---
        # !!! ПРИМІТКА: Вам потрібно буде адаптувати селектори під реальний HTML-код
        # на цільовій сторінці. Це приклад.
        combo_list_container = soup.find('div', class_='daily-combo-section')

        if not combo_list_container:
            logging.warning("Не вдалося знайти блок щоденного комбо (daily-combo-section).")
            # Повертаємо чітке повідомлення про помилку, щоб бот міг його обробити
            return ["Скрапер: Секція не знайдена", "Перевірте HTML-селектори", "Або введіть комбо вручну"]


        combo_items = combo_list_container.find_all(['li', 'div', 'p'], limit=3)

        if len(combo_items) < 3:
            logging.warning(f"Знайдено лише {len(combo_items)} елементів комбо (очікується 3).")
            return ["Скрапер: Неповне комбо", "Знайдено менше 3 елементів", "Перевірте сайт"]


        # Витягуємо чистий текст з кожного елемента
        combo = [item.get_text(strip=True) for item in combo_items]

        if combo and len(combo) == 3:
            logging.info(f"Скрапінг успішний. Нове комбо: {combo}")
            return combo

    except requests.exceptions.RequestException as e:
        logging.error(f"Помилка під час HTTP-запиту: {e}")
        return [f"Помилка HTTP: {e.__class__.__name__}", "Не вдалося підключитися", "Перевірте URL"]
    except Exception as e:
        logging.error(f"Непередбачувана помилка під час скрапінгу: {e}")
        return [f"Непередбачувана помилка: {e.__class__.__name__}", "Зверніться до розробника", ""]

    return None
