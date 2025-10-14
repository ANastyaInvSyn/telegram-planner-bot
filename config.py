import os

# Получаем токен из переменных окружения (для хостинга) или используем локальный
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8392912343:AAH9Cwbsc_6BujWFGXKULrWGgfXg17s4bOc')
TIMEZONE = "Europe/Moscow"
REMINDER_TIMES = [5, 15, 30, 60]

# Для отладки
if os.environ.get('RAILWAY_STATIC_URL'):
    print("Бот запущен на Railway!")
