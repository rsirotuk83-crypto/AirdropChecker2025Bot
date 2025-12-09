import asyncio
import logging
import requests
import json
import time
from bs4 import BeautifulSoup, Tag
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
GLOBAL_COMBO_CARDS: Dict[str, Union[List[str], List[str]]] = {}

# Ініціалізація GLOBAL_COMBO_CARDS заглушками
for game in COMBO_SOURCES:
    GLOBAL_COMBO_CARDS[game] = [f"Скрапер: Комбо для {game} ще не завантажено."]

# --- ФУНКЦІЇ СРАПІНГУ ---

def extract_cards_from_elements(elements: List[Tag]) -> List[str]:
    """Витягує текст карток з знайдених елементів, фільтруючи порожні результати."""
    combo_cards = []
    for element in elements:
        text = element.get_text(strip=True)
        # Уникаємо порожніх рядків та загальних заголовків
        if text and len(text) > 5 and text.lower() not in ["daily combo", "hamster kombat cards", "combo"]:
            combo_cards.append(text)
    return combo_cards

def scrape_for_combo(game_name: str, url: str) -> List[str]:
    """
    Основна функція для скрапінгу комбо з вказаного URL.
    Використовує покращену логіку пошуку селекторів.
    """
    logger.info(f"Починаю скрапінг {game_name} на {url}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() 
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Спроба знайти контейнер, який містить комбо
        # Додаємо більше поширених класів для контейнерів
        combo_container = soup.find('div', class_='combo-cards-list') or \
                          soup.find('div', class_='daily-combo-section') or \
                          soup.find('div', class_='combo-wrapper') or \
                          soup.find('ul', class_='combo-list') or \
                          soup.find('div', class_='entry-content') or \
                          soup.find('div', id='__next') # Часто використовується в сучасних SPA

        if not combo_container:
            return [f"Скрапер: Секція комбо для {game_name} не знайдена."]

        # 2. Спроба знайти елементи карток всередині контейнера
        card_elements = []
        
        # Спроба A: Пошук за елементами списку або картки
        card_elements.extend(combo_container.find_all(['li', 'div'], class_=['combo-card-item', 'card-name', 'combo-item', 'daily-card']))
        
        # Спроба B: Пошук жирного тексту (Strong/B), що часто використовується для назв карток
        if not card_elements:
             card_elements.extend(combo_container.find_all(['strong', 'b', 'h4']))
        
        # Спроба C: Пошук елементів списку (UL/OL)
        if not card_elements:
             card_elements.extend(combo_container.find_all(['li']))
        
        # 3. Обробка та фільтрація результатів
        combo_cards = extract_cards_from_elements(card_elements)

        if len(combo_cards) < 3:
            # Якщо не знайшли 3-4 картки, спробуємо знайти текст напряму в тегах P
            p_tags = combo_container.find_all('p')
            for p_tag in p_tags:
                text = p_tag.get_text(strip=True)
                # Шукаємо шаблони "1. Картка A", "Картка A - Картка B" тощо
                if len(text.split(',')) >= 3 and len(text) > 30: # Якщо схоже на список через кому
                    combo_cards = [c.strip() for c in text.split(',') if c.strip()][:4]
                    break
            
            if len(combo_cards) < 3:
                 return [f"Скрапер: Знайдено лише {len(combo_cards)} карток для {game_name}. Потрібно 3-4. Селектори вимагають ручної корекції."]

        # Обмежуємо до 4 і гарантуємо унікальність
        combo_cards = list(dict.fromkeys(combo_cards[:4]))

        logger.info(f"Скрапінг {game_name} успішно завершено. Знайдено комбо: {combo_cards}")
        return combo_cards

    except requests.RequestException as e:
        logger.error(f"Помилка HTTP під час скрапінгу {game_name}: {e}")
        return [f"Помилка HTTP: Не вдалося підключитися до {url} для {game_name}. {e}"]
    except Exception as e:
        logger.error(f"Невідома помилка скрапінгу {game_name}: {e}")
        return [f"Невідома помилка скрапінгу: {e} для {game_name}"]

# --- ФОНОВИЙ ПЛАНУВАЛЬНИК ---
# ... (Ця частина залишається незмінною, оскільки логіка тут правильна)

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
