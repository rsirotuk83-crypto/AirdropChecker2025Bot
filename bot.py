import requests
from bs4 import BeautifulSoup
import time
import random
import logging

# !!! УВАГА: Якщо ви бачите цю помилку:
# "DefaultBotProperties.__init__() got an unexpected keyword argument 'disable_web_page_preview'"
# Це означає, що вам потрібно виправити ініціалізацію бота у вашому файлі bot.py.
#
# Знайдіть у bot.py рядок:
# from aiogram import Bot
# bot = Bot(token=BOT_TOKEN, parse_mode="HTML", disable_web_page_preview=True) # <-- ЗАСТАРІЛИЙ СИНТАКСИС
#
# І замініть його на ПРАВИЛЬНИЙ СИНТАКСИС (приклад):
# from aiogram import Bot
# from aiogram.client.default import DefaultBotProperties
# from aiogram.enums.parse_mode import ParseMode
#
# def initialize_bot(token):
#     default_properties = DefaultBotProperties(
#         parse_mode=ParseMode.MARKDOWN,
#         disable_web_page_preview=True, # або False, якщо хочете
#         protect_content=False
#     )
#     return Bot(token=token, default=default_properties)
#
# # Виклик:
# # bot = initialize_bot(BOT_TOKEN)
# # -------------------------------------------------------------


# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Список URL-адрес для скрапінгу (для підвищення надійності)
# УВАГА: Ці URL є ПРИКЛАДАМИ. Для реальної роботи потрібно вказати актуальні адреси
# агрегаторів, які ви відстежуєте.
BACKUP_URLS = [
    "https://miningcombo.com/daily-combo-hamster-kombat-today",  # Приклад 1
    "https://tapswapcoin.com/hamster-kombat-combo",              # Приклад 2
    "https://example.com/api/combo.html"                        # Гіпотетичне резервне джерело
]

def fetch_combo_cards(url: str, attempt: int) -> list or None:
    """
    Виконує запит до URL і парсить HTML за допомогою BeautifulSoup.
    
    Args:
        url (str): URL-адреса для скрапінгу.
        attempt (int): Поточна спроба (для логування).
        
    Returns:
        list or None: Список карток комбо або None у разі невдачі.
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        logging.info(f"Спроба {attempt}: Запит до {url}...")
        
        # Виконання HTTP-запиту
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Викликає HTTPError для кодів 4xx/5xx

        # Парсинг HTML за допомогою BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # --- НОВА, БІЛЬШ СТІЙКА ЛОГІКА ПАРСИНГУ ---
        
        # 1. Спробуємо знайти заголовок або контейнер, який містить ключові слова.
        # Шукаємо заголовок, що містить "Daily Combo Cards" або "Комбо"
        combo_header = soup.find(lambda tag: tag.name in ['h2', 'h3', 'p'] and 'combo' in tag.get_text().lower())
        
        cards = []
        if combo_header:
            # 2. Якщо заголовок знайдено, шукаємо найближчий список (ul/ol) або набір параграфів (p)
            # у наступних 5 елементах, де можуть бути картки.
            current_element = combo_header.find_next_sibling()
            count = 0
            while current_element and count < 5:
                # Шукаємо список (ul) і збираємо елементи <li>
                if current_element.name == 'ul' or current_element.name == 'ol':
                    cards = [li.get_text(strip=True) for li in current_element.find_all('li')]
                    break
                
                # Також шукаємо окремі параграфи або div'и, якщо вони містять назви карток
                elif current_element.name in ['p', 'div'] and current_element.get_text(strip=True):
                    # Якщо в одному елементі є декілька рядків, розділених переносом
                    raw_text = current_element.get_text('\n', strip=True)
                    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
                    
                    if len(lines) >= 3 and not cards: # Використовуємо, якщо не знайшли список
                        cards = lines
                        break

                current_element = current_element.find_next_sibling()
                count += 1
        
        # 3. Валідація результату
        if len(cards) >= 3:
            # Обмежуємо до перших трьох карток
            final_cards = cards[:3]
            logging.info(f"Успішно знайдено комбо: {final_cards}")
            return final_cards
        else:
            logging.warning(f"Не вдалося знайти 3 або більше карток комбо. Знайдено: {len(cards)}. Можливо, структура сайту знову змінилася.")
            return None

    except requests.exceptions.HTTPError as e:
        logging.error(f"Помилка HTTP для {url}: {e.response.status_code}. Перехід до наступного URL.")
        return None
    except requests.exceptions.ConnectionError:
        logging.error(f"Помилка з'єднання: Не вдалося підключитися до {url}.")
        return None
    except requests.exceptions.Timeout:
        logging.error(f"Таймаут запиту до {url}.")
        return None
    except Exception as e:
        logging.critical(f"Неочікувана помилка під час парсингу {url}: {e}")
        return None

def main_scheduler():
    """
    Головний планувальник, який періодично викликає функцію скрапінгу.
    """
    COMBO_CARDS = None
    update_interval_seconds = 60 * 60 * 3 # Перевірка кожні 3 години

    logging.info("Планувальник Hamster Kombat запущено.")

    while True:
        try:
            # Лічильник спроб
            attempt_count = 1
            
            # Обхід резервних URL-адрес
            for url in BACKUP_URLS:
                COMBO_CARDS = fetch_combo_cards(url, attempt_count)
                
                if COMBO_CARDS:
                    # Якщо комбо знайдено, виходимо з циклу URL
                    break
                    
                attempt_count += 1
            
            if COMBO_CARDS:
                # Успішне оновлення
                logging.info(f"Останнє актуальне комбо: {COMBO_CARDS}. Чекаю на наступне оновлення.")
                
                # Тут можна додати код для оновлення бази даних (наприклад, Firestore)
                # update_firestore_combo(COMBO_CARDS)
                
            else:
                # Всі URL-адреси не спрацювали
                logging.error("Не вдалося отримати актуальне комбо з жодного джерела.")
            
            # Затримка перед наступною перевіркою
            sleep_time = update_interval_seconds + random.randint(-300, 300) # Додаємо випадковість
            logging.info(f"Сплячка на {sleep_time // 60} хвилин...")
            time.sleep(sleep_time)

        except KeyboardInterrupt:
            logging.warning("Планувальник зупинено користувачем.")
            break
        except Exception as e:
            logging.critical(f"Фатальна помилка планувальника: {e}")
            time.sleep(60) # Коротка пауза, перш ніж спробувати знову

if __name__ == "__main__":
    # Запускаємо основну функцію
    main_scheduler()
