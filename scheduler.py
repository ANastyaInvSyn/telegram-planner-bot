import threading
import time
import datetime
from database import Database
import logging
from config import REMINDER_TIMES

logger = logging.getLogger(__name__)

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
        logger.info("✅ Планировщик запущен")
    
    def stop(self):
        """Остановка планировщика"""
        self.is_running = False
        if self.thread:
            self.thread.join()
        logger.info("🛑 Планировщик остановлен")
    
    def _run(self):
        """Основной цикл планировщика"""
        while self.is_running:
            try:
                self._check_daily_reminders()
                self._check_weekly_reminders()
                self._check_week_transition()
                time.sleep(60)  # Проверяем каждую минуту
            except Exception as e:
                logger.error(f"❌ Ошибка в планировщике: {e}")
                time.sleep(300)
    
    def _check_daily_reminders(self):
        """Проверка ежедневных напоминаний"""
        now = datetime.datetime.now()
        
        for minutes_before in REMINDER_TIMES:
            reminder_time = now + datetime.timedelta(minutes=minutes_before)
            tasks = self.db.get_tasks_for_reminder(reminder_time)
            
            if tasks:
                task_ids = []
                for task in tasks:
                    task_id, user_id, task_text, task_date, task_time, first_name = task
                    task_ids.append(task_id)
                    
                    message = (
                        f"🔔 Напоминание, {first_name}!\n"
                        f"Через {minutes_before} минут:\n"
                        f"📝 {task_text}\n"
                        f"🕐 {task_time}\n"
                        f"📅 {task_date}"
                    )
                    
                    try:
                        self.bot.send_message(chat_id=user_id, text=message)
                        logger.info(f"📨 Напоминание отправлено пользователю {user_id}")
                    except Exception as e:
                        logger.error(f"❌ Не удалось отправить напоминание: {e}")
                
                if task_ids:
                    self.db.mark_as_reminded(task_ids)
    
    def _check_weekly_reminders(self):
        """Проверка ежедневных напоминаний о недельных задачах в 10:00"""
        now = datetime.datetime.now()
        
        if now.hour == 10 and now.minute == 0:
            today = datetime.date.today()
            week_start = self._get_week_start(today)
            
            users = self.db.get_users_for_weekly_reminder()
            
            for user_id in users:
                try:
                    tasks = self.db.get_weekly_tasks(user_id, week_start.strftime('%Y-%m-%d'))
                    if tasks:
                        message = self._format_weekly_reminder(tasks, week_start)
                        self.bot.send_message(chat_id=user_id, text=message)
                        logger.info(f"📨 Недельное напоминание отправлено пользователю {user_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки недельного напоминания: {e}")
    
    def _check_week_transition(self):
        """Проверка перехода на новую неделю (в понедельник в 00:01)"""
        now = datetime.datetime.now()
        
        if now.weekday() == 0 and now.hour == 0 and now.minute == 1:
            last_week = self._get_week_start(datetime.date.today() - datetime.timedelta(days=7))
            current_week = self._get_week_start(datetime.date.today())
            
            self.db.move_uncompleted_weekly_tasks(
                last_week.strftime('%Y-%m-%d'), 
                current_week.strftime('%Y-%m-%d')
            )
            logger.info(f"🔄 Задачи перенесены с {last_week} на {current_week}")
    
    def _get_week_start(self, date):
        """Получить дату начала недели (понедельник)"""
        return date - datetime.timedelta(days=date.weekday())
    
    def _format_weekly_reminder(self, tasks, week_start):
        """Форматирование напоминания о недельных задачах"""
        week_end = week_start + datetime.timedelta(days=6)
        week_range = f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m.%Y')}"
        
        message = f"🗓 Задачи на неделю ({week_range}):\n\n"
        
        completed_count = 0
        for task_id, task_text, completed in tasks:
            if completed:
                message += f"✅ {task_text}\n"
                completed_count += 1
            else:
                message += f"📝 {task_text}\n"
                message += f"   ✓ Выполнить_{task_id}\n\n"
        
        total_count = len(tasks)
        message += f"\n📊 Прогресс: {completed_count}/{total_count} выполнено"
        
        if completed_count < total_count:
            message += "\n\nНе забудьте выполнить оставшиеся задачи! 💪"
        
        return message
