import os
import psycopg2
from datetime import datetime
from typing import List, Tuple, Optional

class Database:
    def __init__(self):
        self.db_url = os.environ.get('DATABASE_URL')
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.conn = psycopg2.connect(self.db_url, sslmode='require')
        self.init_db()
        print("✅ Подключено к PostgreSQL")
    
    def init_db(self):
        """Инициализация базы данных"""
        cursor = self.conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица задач
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                task_text TEXT NOT NULL,
                task_date DATE NOT NULL,
                task_time TIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reminded BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        self.conn.commit()
        cursor.close()
    
    def add_user(self, user_id: int, username: str, first_name: str):
        """Добавление пользователя"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
        ''', (user_id, username, first_name))
        
        self.conn.commit()
        cursor.close()
    
    def add_task(self, user_id: int, task_text: str, task_date: str, task_time: str) -> int:
        """Добавление задачи"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO tasks (user_id, task_text, task_date, task_time)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        ''', (user_id, task_text, task_date, task_time))
        
        task_id = cursor.fetchone()[0]
        self.conn.commit()
        cursor.close()
        return task_id
    
    def get_user_tasks(self, user_id: int, date: str = None) -> List[Tuple]:
        """Получение задач пользователя"""
        cursor = self.conn.cursor()
        
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
    
    def delete_task(self, task_id: int, user_id: int):
        """Удаление задачи"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            DELETE FROM tasks WHERE id = %s AND user_id = %s
        ''', (task_id, user_id))
        
        self.conn.commit()
        cursor.close()
    
    def get_tasks_for_reminder(self, target_datetime: datetime) -> List[Tuple]:
        """Получение задач для напоминания"""
        cursor = self.conn.cursor()
        
        target_date = target_datetime.strftime('%Y-%m-%d')
        target_time = target_datetime.strftime('%H:%M')
        
        cursor.execute('''
            SELECT t.user_id, t.task_text, t.task_date, t.task_time, u.first_name
            FROM tasks t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.task_date = %s AND t.task_time = %s AND t.reminded = FALSE
        ''', (target_date, target_time))
        
        tasks = cursor.fetchall()
        cursor.close()
        return tasks
    
    def mark_as_reminded(self, task_ids: List[int]):
        """Пометить задачи как напомненные"""
        if not task_ids:
            return
            
        cursor = self.conn.cursor()
        
        placeholders = ','.join(['%s'] * len(task_ids))
        cursor.execute(f'''
            UPDATE tasks SET reminded = TRUE 
            WHERE id IN ({placeholders})
        ''', task_ids)
        
        self.conn.commit()
        cursor.close()
