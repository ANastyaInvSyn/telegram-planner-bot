import os
import psycopg2
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных для Railway"""
        try:
            # Railway автоматически предоставляет DATABASE_URL
            database_url = os.environ.get('DATABASE_URL')
            
            if database_url:
                print("🔗 Подключение к PostgreSQL на Railway...")
                
                # Railway использует postgres://, но psycopg2 требует postgresql://
                if database_url.startswith('postgres://'):
                    database_url = database_url.replace('postgres://', 'postgresql://', 1)
                
                self.conn = psycopg2.connect(database_url)
                self._create_tables()
                print("✅ Успешно подключено к PostgreSQL на Railway")
                
                # Проверка подключения
                cursor = self.conn.cursor()
                cursor.execute("SELECT version();")
                db_version = cursor.fetchone()
                print(f"🔍 Версия PostgreSQL: {db_version[0]}")
                cursor.close()
                
            else:
                print("❌ DATABASE_URL не найден")
                
        except Exception as e:
            print(f"❌ Ошибка подключения к базе: {e}")
    
    def _create_tables(self):
        """Создание таблиц если их нет"""
        if not self.conn:
            return
            
        cursor = self.conn.cursor()
        
        try:
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица ежедневных задач
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    task_text TEXT NOT NULL,
                    task_date DATE NOT NULL,
                    task_time TIME NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reminded BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            ''')
            
            # Таблица недельных задач
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS weekly_tasks (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    task_text TEXT NOT NULL,
                    week_start DATE NOT NULL,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            ''')
            
            self.conn.commit()
            cursor.close()
            print("✅ Таблицы созданы/проверены")
            
        except Exception as e:
            print(f"❌ Ошибка создания таблиц: {e}")
            self.conn.rollback()
    
    def _execute_query(self, query: str, params: tuple = None, return_result: bool = False):
        """Безопасное выполнение запроса"""
        if not self.conn:
            return None
            
        cursor = self.conn.cursor()
        try:
            cursor.execute(query, params or ())
            if return_result:
                result = cursor.fetchone()
                self.conn.commit()
                cursor.close()
                return result
            else:
                self.conn.commit()
                cursor.close()
                return cursor
        except Exception as e:
            logger.error(f"Ошибка базы: {e}")
            self.conn.rollback()
            return None
    
    # === МЕТОДЫ ДЛЯ ЕЖЕДНЕВНЫХ ЗАДАЧ ===
    
    def add_user(self, user_id: int, username: str, first_name: str):
        cursor = self._execute_query('''
            INSERT INTO users (user_id, username, first_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
        ''', (user_id, username, first_name))
        if cursor:
            cursor.close()
    
    def add_task(self, user_id: int, task_text: str, task_date: str, task_time: str) -> int:
        result = self._execute_query('''
            INSERT INTO tasks (user_id, task_text, task_date, task_time)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        ''', (user_id, task_text, task_date, task_time), return_result=True)
        
        if result:
            return result[0]
        return 0
    
    def get_user_tasks(self, user_id: int, date: str = None) -> List[Tuple]:
        if not self.conn:
            return []
            
        cursor = self.conn.cursor()
        try:
            if date:
                cursor.execute('''
                    SELECT id, task_text, task_time FROM tasks 
                    WHERE user_id = %s AND task_date = %s 
                    ORDER BY task_time
                ''', (user_id, date))
            else:
                cursor.execute('''
                    SELECT id, task_text, task_date, task_time FROM tasks 
                    WHERE user_id = %s 
                    ORDER BY task_date, task_time
                ''', (user_id,))
            
            tasks = cursor.fetchall()
            cursor.close()
            return tasks
            
        except Exception as e:
            logger.error(f"Ошибка получения задач: {e}")
            return []
    
    def delete_task(self, task_id: int, user_id: int):
        self._execute_query('''
            DELETE FROM tasks WHERE id = %s AND user_id = %s
        ''', (task_id, user_id))
    
    def get_tasks_for_reminder(self, target_datetime: datetime) -> List[Tuple]:
        if not self.conn:
            return []
            
        cursor = self.conn.cursor()
        try:
            target_date = target_datetime.strftime('%Y-%m-%d')
            target_time = target_datetime.strftime('%H:%M')
            
            cursor.execute('''
                SELECT t.id, t.user_id, t.task_text, t.task_date, t.task_time, u.first_name
                FROM tasks t
                JOIN users u ON t.user_id = u.user_id
                WHERE t.task_date = %s AND t.task_time = %s AND t.reminded = FALSE
            ''', (target_date, target_time))
            
            tasks = cursor.fetchall()
            cursor.close()
            return tasks
        except Exception as e:
            logger.error(f"Ошибка получения напоминаний: {e}")
            return []
    
    def mark_as_reminded(self, task_ids: List[int]):
        if self.conn and task_ids:
            cursor = self.conn.cursor()
            try:
                placeholders = ','.join(['%s'] * len(task_ids))
                cursor.execute(f'''
                    UPDATE tasks SET reminded = TRUE 
                    WHERE id IN ({placeholders})
                ''', task_ids)
                self.conn.commit()
                cursor.close()
            except Exception as e:
                logger.error(f"Ошибка отметки напоминаний: {e}")
                self.conn.rollback()
    
    # === МЕТОДЫ ДЛЯ НЕДЕЛЬНЫХ ЗАДАЧ ===
    
    def add_weekly_task(self, user_id: int, task_text: str, week_start: str) -> int:
        result = self._execute_query('''
            INSERT INTO weekly_tasks (user_id, task_text, week_start)
            VALUES (%s, %s, %s)
            RETURNING id
        ''', (user_id, task_text, week_start), return_result=True)
        
        if result:
            return result[0]
        return 0
    
    def get_weekly_tasks(self, user_id: int, week_start: str) -> List[Tuple]:
        if not self.conn:
            return []
            
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                SELECT id, task_text, completed 
                FROM weekly_tasks 
                WHERE user_id = %s AND week_start = %s 
                ORDER BY created_at
            ''', (user_id, week_start))
            
            tasks = cursor.fetchall()
            cursor.close()
            return tasks
        except Exception as e:
            logger.error(f"Ошибка получения недельных задач: {e}")
            return []
    
    def complete_weekly_task(self, task_id: int, user_id: int):
        self._execute_query('''
            UPDATE weekly_tasks 
            SET completed = TRUE 
            WHERE id = %s AND user_id = %s
        ''', (task_id, user_id))
    
    def delete_weekly_task(self, task_id: int, user_id: int):
        self._execute_query('''
            DELETE FROM weekly_tasks 
            WHERE id = %s AND user_id = %s
        ''', (task_id, user_id))
    
    def move_uncompleted_weekly_tasks(self, from_week: str, to_week: str):
        self._execute_query('''
            UPDATE weekly_tasks 
            SET week_start = %s, completed = FALSE
            WHERE week_start = %s AND completed = FALSE
        ''', (to_week, from_week))
    
    def get_users_for_weekly_reminder(self):
        if not self.conn:
            return []
            
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                SELECT DISTINCT user_id 
                FROM weekly_tasks 
                WHERE completed = FALSE
            ''')
            
            users = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return users
        except Exception as e:
            logger.error(f"Ошибка получения пользователей: {e}")
            return []
