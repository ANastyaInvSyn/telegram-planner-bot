import os

# Получаем токен из переменных окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения!")

TIMEZONE = "Europe/Moscow"
REMINDER_TIMES = [5, 15, 30, 60]  # За сколько минут напоминать

print("✅ Конфигурация загружена успешно")
