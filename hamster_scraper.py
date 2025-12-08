import time
import requests
import logging
import asyncio 
from bs4 import BeautifulSoup
from typing import List

# Налаштування логування
logger = logging.getLogger(__name__)

# --- КРИТИЧНО ВАЖЛИВА ГЛОБАЛЬНА ЗМІННА ---
# Ця змінна КРИТИЧНО потрібна боту. Вона буде оновлюватися планувальником
# і читатися хендлером `get_combo_data_handler` у bot.py.
GLOBAL_COMBO_CARDS: List[str] = []
# -----------------------------------------------

def _scrape_from_miningcombo() -> List[str]:
    """Спроба 1: Скрапінг з miningcombo.com"""
    try:
        # Встановлено URL-адресу, яку було визнано найбільш надійним джерелом
        url = "https://miningcombo.com/daily-combo-hamster-kombat-today/"
        logger.info(f"Спроба 1: Запит до {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Виконання синхронного HTTP-запиту
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Викликає виняток для поганих кодів стану (4xx або 5xx)
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Цільовий клас div, який, як відомо, містить список комбо-карток
        combo_div = soup.find('div', class_='daily-combo-list') 
        
        if not combo_div:
            logger.warning("Не вдалося знайти div.daily-combo-list. Спроба пошуку li.")
            # Резервний пошук, якщо основний клас зміниться
            list_items = soup.find_all('li')
            cards = [item.text.strip() for item in list_items if len(item.text.strip()) > 5 and 'Upgrade' in item.text]
        else:
            # Отримання тексту з усіх елементів списку
            cards = [li.text.strip() for li in combo_div.find_all('li') if li.text.strip()]

        # Фільтрація, щоб залишити лише реальні картки (зазвичай 3 картки)
        filtered_cards = [card for card in cards if card and len(card.split()) > 1]
        
        if len(filtered_cards) >= 3:
            logger.info(f"Знайдено: {len(filtered_cards)} карток. Використовуємо перші три.")
            return filtered_cards[:3]

        logger.warning(f"Не вдалося знайти 3 або більше карток комбо. Знайдено: {len(filtered_cards)}. Структура сайту, можливо, змінилася.")
        return []

    except requests.exceptions.RequestException as e:
        logger.error(f"Помилка HTTP для miningcombo.com: {e}")
        return []

def _scrape_for_combo() -> List[str]:
    """Центральна функція для отримання комбо. Може розширюватися іншими скреперами."""
    combo = _scrape_from_miningcombo()
    if len(combo) == 3:
        return combo
    
    logger.error("Не вдалося отримати актуальне комбо з жодного джерела.")
    return []

async def main_scheduler():
    """КРИТИЧНО ВАЖЛИВА ФУНКЦІЯ: Асинхронний планувальник, який запускається у фоновому режимі."""
    global GLOBAL_COMBO_CARDS
    
    logger.info("Планувальник Hamster Kombat запущено.")
    
    # Виконуємо перше завантаження одразу при старті
    # Використання asyncio.to_thread для запуску синхронної функції скрапінгу
    new_combo = await asyncio.to_thread(_scrape_for_combo) 
    if new_combo:
        GLOBAL_COMBO_CARDS = new_combo
        logger.info(f"Перше завантаження успішне. Комбо: {GLOBAL_COMBO_CARDS}")
    
    # Нескінченний цикл оновлення (раз на 3 години)
    while True:
        # Інтервал оновлення 3 години (3 * 60 хвилин * 60 секунд)
        sleep_time = 3 * 60 * 60 
        logger.info(f"Сплячка на {sleep_time // 60} хвилин перед наступним скрапінгом...")
        await asyncio.sleep(sleep_time) 
        
        new_combo = await asyncio.to_thread(_scrape_for_combo)
        if new_combo:
            GLOBAL_COMBO_CARDS = new_combo
            logger.info(f"Оновлення успішне. Нове комбо: {GLOBAL_COMBO_CARDS}")
        else:
            logger.warning("Оновлення не вдалося. Залишаємо старі дані.")

if __name__ == "__main__":
    # Тестовий запуск для локального виконання
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    print("--- Починаю тестовий запуск скрапера ---")
    combo_result = _scrape_for_combo()
    print(f"Test run result: {combo_result}")
    print("--- Тестовий запуск завершено ---")
