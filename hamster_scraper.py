import asyncio
import logging
import requests
import json
from bs4 import BeautifulSoup
from typing import List

# Налаштування логування
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- КОНСТАНТИ ---
# URL, який ми скрапимо для TON Station
TON_STATION_URL = "https://miningcombo.com/ton-station/"

# Глобальна змінна для зберігання комбо-карток. 
# bot.py використовує її для передачі даних між скрапером та Telegram.
# Ініціалізуємо її як порожній список.
GLOBAL_COMBO_CARDS: List[str] = []

# --- ФУНКЦІЇ СРАПІНГУ ---

def scrape_for_combo() -> List[str]:
    """
    Основна функція для скрапінгу комбо з TON_STATION_URL.
    
    УВАГА: Цю функцію потрібно адаптувати, якщо структура сайту зміниться!
    """
    logger.info(f"Починаю скрапінг TON Station на {TON_STATION_URL} для оновлення комбо (4 карт)...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # 1. Запит до сторінки
        response = requests.get(TON_STATION_URL, headers=headers, timeout=15)
        response.raise_for_status() # Викликає виняток для поганих кодів (4xx або 5xx)
        
        # 2. Парсинг HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # --- КРИТИЧНА СЕКЦІЯ: ВИЗНАЧЕННЯ СЕЛЕКТОРІВ ---
        
        # Вам потрібно перевірити актуальний HTML сторінки 
        # (наприклад, через F12 у браузері) і знайти актуальний селектор.
        # Шукаємо елемент, який містить список карток. Наприклад, це може бути div з ID чи класом.
        
        # Приклад 1: Якщо комбо обгорнуте в div з класом 'combo-list'
        combo_container = soup.find('div', class_='combo-cards-list')
        
        if not combo_container:
            # Спроба знайти за іншим, більш загальним тегом
            combo_container = soup.find('section', id='daily-combo-section')

        if not combo_container:
            # Це і є ваша помилка: "Секція комбо не знайдена на сторінці."
            return [f"Скрапер: Секція комбо не знайдена на сторінці {TON_STATION_URL}. Перевірте селектор."]

        # 3. Витягування окремих карток
        # Припускаємо, що кожна картка — це елемент 'li' або 'div' всередині контейнера.
        # Використовуйте максимально точний селектор для елементів карток:
        card_elements = combo_container.find_all('li', class_='combo-card-item') 
        
        # Якщо card_elements порожній, спробуйте інший селектор (наприклад, 'p' або 'div')
        if not card_elements:
             # Наприклад, якщо картки просто в тегах <b>
             card_elements = combo_container.find_all('b') 

        if not card_elements:
             return [f"Скрапер: Знайдено контейнер, але не знайдено елементів карток всередині."]
             
        # 4. Формування списку результатів
        combo_cards = [
            element.get_text(strip=True)
            for element in card_elements
        ]
        
        # Обмежуємо до 4 карток, якщо знайдено більше
        combo_cards = combo_cards[:4]

        if not combo_cards or len(combo_cards) < 4:
            return [f"Скрапер: Знайдено лише {len(combo_cards)} карток. Очікується 4."]
            
        logger.info(f"Скрапінг успішно завершено. Знайдено комбо: {combo_cards}")
        return combo_cards

    except requests.RequestException as e:
        logger.error(f"Помилка HTTP під час скрапінгу: {e}")
        return [f"Помилка HTTP: Не вдалося підключитися до {TON_STATION_URL}. {e}"]
    except Exception as e:
        logger.error(f"Невідома помилка скрапінгу: {e}")
        return [f"Невідома помилка скрапінгу: {e}"]

# --- ФОНОВИЙ ПЛАНУВАЛЬНИК ---

async def main_scheduler():
    """
    Запускає скрапінг комбо кожні 15 хвилин і оновлює глобальну змінну.
    """
    global GLOBAL_COMBO_CARDS
    
    # Спроба першого запуску при старті
    initial_combo = scrape_for_combo()
    if initial_combo and not initial_combo[0].startswith("Скрапер:"):
        GLOBAL_COMBO_CARDS[:] = initial_combo
        logger.info(f"Ініціалізація GLOBAL_COMBO_CARDS при старті: {GLOBAL_COMBO_CARDS}")
    else:
        GLOBAL_COMBO_CARDS[:] = ["Скрапер: Не встановлено (помилка при старті)."]
        logger.warning(f"Ініціалізація GLOBAL_COMBO_CARDS не вдалася: {initial_combo[0]}")
        
    
    while True:
        # Чекаємо 15 хвилин
        await asyncio.sleep(15 * 60)
        
        try:
            new_combo = await asyncio.to_thread(scrape_for_combo)
            
            # Якщо результат не є повідомленням про помилку
            if new_combo and not new_combo[0].startswith("Скрапер:") and not new_combo[0].startswith("Помилка HTTP:"):
                # Оновлюємо глобальну змінну лише у разі успіху
                GLOBAL_COMBO_CARDS[:] = new_combo
                logger.info(f"Комбо оновлено планувальником: {GLOBAL_COMBO_CARDS}")
            else:
                logger.warning(f"Комбо не оновлено через помилку: {new_combo[0]}")
                
        except Exception as e:
            logger.error(f"Критична помилка в планувальнику: {e}")

if __name__ == "__main__":
    # Логіка для тестування скрапера локально
    print("--- Тестування Scraper ---")
    result = scrape_for_combo()
    print("Результат:", result)
    if result and result[0].startswith("Скрапер:"):
        print("Помилка: Необхідно оновити селектори в scrape_for_combo.")
    print("-------------------------")
