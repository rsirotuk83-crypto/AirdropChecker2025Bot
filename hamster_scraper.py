import asyncio
import logging
import requests
import json
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Union

# Налаштування логування
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- КОНСТАНТИ ТА КОНФІГУРАЦІЯ ІГОР ---
COMBO_SOURCES: Dict[str, str] = {
    # Game: URL (4-карткове комбо)
    "TON Station": "https://miningcombo.com/ton-station/",
    "Hamster Kombat": "https://hamster-combo.com/",
    "TapSwap": "https://miningcombo.com/tapswap-2/",
    "Blum": "https://miningcombo.com/blum-2/",
    "Cattea": "https://miningcombo.com/cattea/",
}

# Глобальна змінна для зберігання всіх комбо. 
# Ключ: назва гри, Значення: List[str] або List[str помилки]
GLOBAL_COMBO_CARDS: Dict[str, Union[List[str], List[str]]] = {}

# Ініціалізація GLOBAL_COMBO_CARDS заглушками
for game in COMBO_SOURCES:
    GLOBAL_COMBO_CARDS[game] = [f"Скрапер: Комбо для {game} ще не завантажено."]

# --- ФУНКЦІЇ СРАПІНГУ ---

def scrape_for_combo(game_name: str, url: str) -> List[str]:
    """
    Основна функція для скрапінгу комбо з вказаного URL.
    
    УВАГА: Селектори (combo_container, card_elements) можуть потребувати налаштування 
    для кожної окремої сторінки, якщо їхня HTML-структура різна!
    """
    logger.info(f"Починаю скрапінг {game_name} на {url}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # 1. Запит до сторінки
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() 
        
        # 2. Парсинг HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # --- КРИТИЧНА СЕКЦІЯ: ВИЗНАЧЕННЯ СЕЛЕКТОРІВ ---
        
        # Універсальні спроби пошуку:
        
        # 1. Пошук контейнера комбо за поширеними класами
        combo_container = soup.find('div', class_='combo-cards-list') or \
                          soup.find('div', class_='daily-combo-section') or \
                          soup.find('section', id='daily-combo-section') or \
                          soup.find('div', class_='combo-wrapper')
        
        if not combo_container:
            # Це сигнал, що селектори потрібно адаптувати
            return [f"Скрапер: Секція комбо для {game_name} не знайдена."]

        # 2. Пошук елементів карток всередині контейнера
        # Спроба знайти елементи списку або параграфи, що містять назви карток
        card_elements = combo_container.find_all('li', class_='combo-card-item') or \
                        combo_container.find_all('div', class_='card-name') or \
                        combo_container.find_all('p')
                        
        if not card_elements:
             return [f"Скрапер: Знайдено контейнер, але не знайдено елементів карток всередині для {game_name}."]
             
        # 3. Формування списку результатів
        combo_cards = [
            element.get_text(strip=True)
            for element in card_elements if element.get_text(strip=True)
        ]
        
        # Більшість комбо складається з 3-4 карт. Обмежуємо або перевіряємо мінімум.
        if len(combo_cards) < 3:
            return [f"Скрапер: Знайдено лише {len(combo_cards)} карток для {game_name}. Очікується 3-4."]
        
        # Обмежуємо до 4
        combo_cards = combo_cards[:4]

        logger.info(f"Скрапінг {game_name} успішно завершено. Знайдено комбо: {combo_cards}")
        return combo_cards

    except requests.RequestException as e:
        logger.error(f"Помилка HTTP під час скрапінгу {game_name}: {e}")
        return [f"Помилка HTTP: Не вдалося підключитися до {url} для {game_name}. {e}"]
    except Exception as e:
        logger.error(f"Невідома помилка скрапінгу {game_name}: {e}")
        return [f"Невідома помилка скрапінгу: {e} для {game_name}"]

# --- ФОНОВИЙ ПЛАНУВАЛЬНИК ---

async def main_scheduler():
    """
    Запускає скрапінг для всіх ігор і оновлює глобальну змінну.
    """
    global GLOBAL_COMBO_CARDS
    
    logger.info("Запуск первинного скрапінгу для всіх ігор...")
    
    # Первинний запуск (синхронно)
    for game_name, url in COMBO_SOURCES.items():
        result = scrape_for_combo(game_name, url)
        GLOBAL_COMBO_CARDS[game_name] = result
        if result and not result[0].startswith("Скрапер:"):
            logger.info(f"Ініціалізація {game_name} успішна.")
        else:
            logger.warning(f"Ініціалізація {game_name} не вдалася: {result[0]}")
    
    # Цикл планувальника (асинхронно)
    while True:
        # Чекаємо 15 хвилин
        await asyncio.sleep(15 * 60)
        
        logger.info("Планувальник: Починаю періодичне оновлення комбо.")
        
        for game_name, url in COMBO_SOURCES.items():
            try:
                # Виконуємо синхронну функцію в окремому потоці
                new_combo = await asyncio.to_thread(scrape_for_combo, game_name, url)
                
                # Якщо результат не є повідомленням про помилку
                if new_combo and not new_combo[0].startswith("Скрапер:") and not new_combo[0].startswith("Помилка HTTP:"):
                    GLOBAL_COMBO_CARDS[game_name] = new_combo
                    logger.info(f"Планувальник: Комбо для {game_name} оновлено.")
                else:
                    logger.warning(f"Планувальник: Комбо для {game_name} не оновлено. Причина: {new_combo[0]}")
                    
            except Exception as e:
                logger.error(f"Критична помилка в планувальнику для {game_name}: {e}")

if __name__ == "__main__":
    # Логіка для тестування скрапера локально
    print("--- Тестування Scraper ---")
    for game_name, url in COMBO_SOURCES.items():
        result = scrape_for_combo(game_name, url)
        print(f"Результат для {game_name}: {result}")
    print("-------------------------")
