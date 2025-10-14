import threading
import time
import datetime
from database import Database
import logging
from config import REMINDER_TIMES
import logging

class Scheduler:
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.is_running = False
        self.thread = None
    
    def start(self):
        """Запуск планировщика в отдельном потоке"""
        self.is_running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        logging.info("Планировщик напоминаний запущен")
    
    def stop(self):
        """Остановка планировщика"""
        self.is_running = False
        if self.thread:
            self.thread.join()
        logging.info("Планировщик напоминаний остановлен")
    
    def _run(self):
        """Основной цикл планировщика"""
        while self.is_running:
            try:
                self._check_reminders()
                time.sleep(30)  # Проверяем каждые 30 секунд
            except Exception as e:
                logging.error(f"Ошибка в планировщике: {e}")
                time.sleep(60)
    
    def _check_reminders(self):
        """Проверка напоминаний"""
        now = datetime.datetime.now()
        
        for minutes_before in REMINDER_TIMES:
            reminder_time = now + datetime.timedelta(minutes=minutes_before)
            
            # Получаем задачи на это время
            tasks = self.db.get_tasks_for_reminder(reminder_time)
            
            if tasks:
                task_ids = []
                for task in tasks:
                    user_id, task_text, task_date, task_time, first_name = task
                    task_ids.append(task[0])  # ID задачи
                    
                    # Формируем сообщение
                    message = (
                        f"🔔 Напоминание!\n"
                        f"Через {minutes_before} минут:\n"
                        f"📝 {task_text}\n"
                        f"🕐 {task_time}\n"
                        f"📅 {task_date}"
                    )
                    
                    # Отправляем напоминание
                    try:
                        self.bot.send_message(
                            chat_id=user_id,
                            text=message
                        )
                        logging.info(f"Напоминание отправлено пользователю {user_id}")
                    except Exception as e:
                        logging.error(f"Не удалось отправить напоминание: {e}")
                
                # Помечаем задачи как напомненные

                self.db.mark_as_reminded(task_ids)
