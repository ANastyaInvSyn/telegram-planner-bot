import os

# Получаем токен из переменных окружения (для хостинга) или используем локальный
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8392912343:AAH9Cwbsc_6BujWFGXKULrWGgfXg17s4bOc')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

TIMEZONE = "Europe/Moscow"
REMINDER_TIMES = [5, 15, 30, 60]  # За сколько минут напоминать о ежедневных задачах

print("✅ Конфигурация загружена успешно")
