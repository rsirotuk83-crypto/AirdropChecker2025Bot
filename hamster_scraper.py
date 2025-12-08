import requests
from bs4 import BeautifulSoup
import logging
from typing import List
import time
import asyncio

# Глобальна змінна для зберігання актуальних карток.
# Імпортується у bot.py
GLOBAL_COMBO_CARDS: List[str] = []

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URL, який будемо скрапити. 
# Замініть на точний URL, де публікується щоденне комбо Hamster Kombat.
# У цьому прикладі використовується загальний URL.
TARGET_URL = "https://hamsterkombat.io/" 

def _scrape_for_combo() -> List[str] | None:
    """Виконує синхронний скрапінг для отримання щоденного комбо."""
    try:
        logging.info("Починаю скрапінг Hamster Kombat для оновлення комбо...")
        
        # Використовуємо User-Agent, щоб імітувати браузер та уникнути блокування
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }
        
        response = requests.get(TARGET_URL, headers=headers, timeout=15)
        response.raise_for_status() # Викликає помилку для поганих статусів (4xx або 5xx)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- КРИТИЧНА ЛОГІКА СЕЛЕКТОРІВ ---
        # Вам, можливо, доведеться змінити ці селектори, коли дізнаєтеся,
        # як саме виглядає HTML на цільовій сторінці.
        
        # Приклад: шукаємо блок, який містить комбо
        combo_list_container = soup.find('div', class_='daily-combo-section')
        
        if not combo_list_container:
            logging.warning("Не вдалося знайти блок щоденного комбо на цільовій сторінці.")
            return ["Помилка: Секція не знайдена", "Спробуйте пізніше", "Або введіть вручну"]


        # Приклад: витягуємо текст з трьох елементів (наприклад, <li> або <div>)
        # всередині знайденого контейнера.
        combo_items = combo_list_container.find_all(['li', 'div', 'p'], limit=3) 
        
        if len(combo_items) < 3:
            logging.warning(f"Знайдено лише {len(combo_items)} елементів комбо (очікується 3).")
            return ["Помилка: Неповне комбо", "Перевірте HTML", "Сайт змінився"]
            
        
        # Витягуємо чистий текст з кожного елемента
        combo = [item.get_text(strip=True) for item in combo_items]
        
        if combo and len(combo) == 3:
            logging.info(f"Скрапінг успішний. Нове комбо: {combo}")
            return combo
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Помилка під час HTTP-запиту: {e}")
    except Exception as e:
        logging.error(f"Непередбачувана помилка під час скрапінгу: {e}")
        
    return None

async def main_scheduler():
    """Фоновий планувальник, який запускає скрапінг регулярно."""
    global GLOBAL_COMBO_CARDS
    
    # Інтервал оновлення в секундах (3 години = 10800 секунд)
    UPDATE_INTERVAL_SECONDS = 3 * 60 * 60 

    while True:
        try:
            # Запускаємо синхронну функцію в окремому потоці (для неблокування aiohttp)
            new_combo = await asyncio.to_thread(_scrape_for_combo)
            
            if new_combo and new_combo[0] not in ["Помилка: Секція не знайдена", "Помилка: Неповне комбо"]:
                GLOBAL_COMBO_CARDS[:] = new_combo # Оновлюємо глобальну змінну
                
                # Оновлюємо базу даних через імпорт з bot.py
                try:
                    from bot import db
                    db.set_global_combo(new_combo)
                    logging.info("Комбо успішно збережено у BotDB.")
                except ImportError:
                    logging.warning("Не вдалося імпортувати BotDB з bot.py для збереження.")
                    
            else:
                logging.warning("Скрапінг не знайшов нового комбо. Використовуються старі дані.")
                
        except Exception as e:
            logging.error(f"Помилка у планувальнику скрапінгу: {e}")
            
        logging.info(f"Сплячка на {UPDATE_INTERVAL_SECONDS // 3600} годин перед наступним скрапінгом...")
        await asyncio.sleep(UPDATE_INTERVAL_SECONDS)

if __name__ == "__main__":
    # Для тестування скрапера локально:
    print(f"Результат скрапінгу: {_scrape_for_combo()}")
