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
        """Инициализация базы данных для Render"""
        try:
            database_url = os.environ.get('DATABASE_URL')
            
            if database_url:
                print(f"🔗 Найден DATABASE_URL: {database_url[:50]}...")
                
                if database_url.startswith('postgres://'):
                    database_url = database_url.replace('postgres://', 'postgresql://', 1)
                    print("✅ Формат URL исправлен для psycopg2")
                
                self.conn = psycopg2.connect(database_url, sslmode='require')
                self._create_tables()
                print("✅ Успешно подключено к PostgreSQL на Render")
                
            else:
                print("❌ DATABASE_URL не найден в переменных окружения")
                
        except Exception as e:
            print(f"❌ Ошибка подключения к базе данных: {e}")
    
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
            print("✅ Таблицы успешно созданы/проверены")
            
        except Exception as e:
            print(f"❌ Ошибка при создании таблиц: {e}")
            self.conn.rollback()
    
    # === МЕТОДЫ ДЛЯ ЕЖЕДНЕВНЫХ ЗАДАЧ ===
    
    def add_user(self, user_id: int, username: str, first_name: str):
        if self.conn:
            cursor = self.conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (user_id, username, first_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                ''', (user_id, username, first_name))
                self.conn.commit()
                cursor.close()
            except Exception as e:
                print(f"❌ Ошибка добавления пользователя: {e}")
                self.conn.rollback()
    
    def add_task(self, user_id: int, task_text: str, task_date: str, task_time: str) -> int:
        if self.conn:
            cursor = self.conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO tasks (user_id, task_text, task_date, task_time)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                ''', (user_id, task_text, task_date, task_time))
                
                task_id = cursor.fetchone()[0]
                self.conn.commit()
                cursor.close()
                print(f"✅ Ежедневная задача добавлена с ID: {task_id}")
                return task_id
                
            except Exception as e:
                print(f"❌ Ошибка добавления ежедневной задачи: {e}")
                self.conn.rollback()
                return 0
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
            print(f"❌ Ошибка получения ежедневных задач: {e}")
            return []
    
    def delete_task(self, task_id: int, user_id: int):
        if self.conn:
            cursor = self.conn.cursor()
            try:
                cursor.execute('''
                    DELETE FROM tasks WHERE id = %s AND user_id = %s
                ''', (task_id, user_id))
                self.conn.commit()
                cursor.close()
                print(f"✅ Ежедневная задача {task_id} удалена")
            except Exception as e:
                print(f"❌ Ошибка удаления ежедневной задачи: {e}")
                self.conn.rollback()
    
    # === МЕТОДЫ ДЛЯ НЕДЕЛЬНЫХ ЗАДАЧ ===
    
    def add_weekly_task(self, user_id: int, task_text: str, week_start: str) -> int:
        """Добавить недельную задачу"""
        if self.conn:
            cursor = self.conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO weekly_tasks (user_id, task_text, week_start)
                    VALUES (%s, %s, %s)
                    RETURNING id
                ''', (user_id, task_text, week_start))
                
                task_id = cursor.fetchone()[0]
                self.conn.commit()
                cursor.close()
                print(f"✅ Недельная задача добавлена с ID: {task_id}")
                return task_id
                
            except Exception as e:
                print(f"❌ Ошибка добавления недельной задачи: {e}")
                self.conn.rollback()
                return 0
        return 0
    
    def get_weekly_tasks(self, user_id: int, week_start: str) -> List[Tuple]:
        """Получить недельные задачи для пользователя и недели"""
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
            print(f"❌ Ошибка получения недельных задач: {e}")
            return []
    
    def complete_weekly_task(self, task_id: int, user_id: int):
        """Отметить недельную задачу как выполненную"""
        if self.conn:
            cursor = self.conn.cursor()
            try:
                cursor.execute('''
                    UPDATE weekly_tasks 
                    SET completed = TRUE 
                    WHERE id = %s AND user_id = %s
                ''', (task_id, user_id))
                
                self.conn.commit()
                cursor.close()
                print(f"✅ Недельная задача {task_id} отмечена как выполненная")
                
            except Exception as e:
                print(f"❌ Ошибка отметки недельной задачи: {e}")
                self.conn.rollback()
    
    def delete_weekly_task(self, task_id: int, user_id: int):
        """Удалить недельную задачу"""
        if self.conn:
            cursor = self.conn.cursor()
            try:
                cursor.execute('''
                    DELETE FROM weekly_tasks 
                    WHERE id = %s AND user_id = %s
                ''', (task_id, user_id))
                
                self.conn.commit()
                cursor.close()
                print(f"✅ Недельная задача {task_id} удалена")
                
            except Exception as e:
                print(f"❌ Ошибка удаления недельной задачи: {e}")
                self.conn.rollback()
    
    def move_uncompleted_weekly_tasks(self, from_week: str, to_week: str):
        """Перенести невыполненные задачи на следующую неделю"""
        if self.conn:
            cursor = self.conn.cursor()
            try:
                cursor.execute('''
                    UPDATE weekly_tasks 
                    SET week_start = %s, completed = FALSE
                    WHERE week_start = %s AND completed = FALSE
                ''', (to_week, from_week))
                
                self.conn.commit()
                cursor.close()
                print(f"✅ Невыполненные задачи перенесены с {from_week} на {to_week}")
                
            except Exception as e:
                print(f"❌ Ошибка переноса недельных задач: {e}")
                self.conn.rollback()
    
    def get_users_for_weekly_reminder(self):
        """Получить всех пользователей, у которых есть активные недельные задачи"""
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
            print(f"❌ Ошибка получения пользователей для напоминания: {e}")
            return []
