# Використовуємо офіційний образ Python
FROM python:3.11-slim

# Встановлюємо робочий каталог у контейнері
WORKDIR /app

# Копіюємо файл залежностей та встановлюємо їх
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо всі файли проекту (bot.py, hamster_scraper.py і т.д.)
COPY . .

# Визначаємо команду для запуску бота, як і в railway.toml
CMD ["python", "bot.py"]
