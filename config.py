import os

# Получаем токен из переменных окружения (для хостинга) или используем локальный
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8392912343:AAH9Cwbsc_6BujWFGXKULrWGgfXg17s4bOc')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения!")

TIMEZONE = "Europe/Moscow"
REMINDER_TIMES = [5, 15, 30, 60]

print("✅ Конфигурация загружена успешно")
