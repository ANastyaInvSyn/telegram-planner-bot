import sqlite3
import datetime
from typing import List, Tuple, Optional

class Database:
    def __init__(self, db_name="planner_bot.db"):
        self.db_name = db_name
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица задач
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_text TEXT NOT NULL,
                task_date DATE NOT NULL,
                task_time TIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reminded BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: str, first_name: str):
        """Добавление пользователя"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))
        
        conn.commit()
        conn.close()
    
    def add_task(self, user_id: int, task_text: str, task_date: str, task_time: str) -> int:
        """Добавление задачи"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO tasks (user_id, task_text, task_date, task_time)
            VALUES (?, ?, ?, ?)
        ''', (user_id, task_text, task_date, task_time))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id
    
    def get_user_tasks(self, user_id: int, date: str = None) -> List[Tuple]:
        """Получение задач пользователя"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        if date:
            cursor.execute('''
                SELECT id, task_text, task_time FROM tasks 
                WHERE user_id = ? AND task_date = ? 
                ORDER BY task_time
            ''', (user_id, date))
        else:
            cursor.execute('''
                SELECT id, task_text, task_date, task_time FROM tasks 
                WHERE user_id = ? 
                ORDER BY task_date, task_time
            ''', (user_id,))
        
        tasks = cursor.fetchall()
        conn.close()
        return tasks
    
    def delete_task(self, task_id: int, user_id: int):
        """Удаление задачи"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM tasks WHERE id = ? AND user_id = ?
        ''', (task_id, user_id))
        
        conn.commit()
        conn.close()
    
    def get_tasks_for_reminder(self, target_datetime: datetime.datetime) -> List[Tuple]:
        """Получение задач для напоминания"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        target_date = target_datetime.strftime('%Y-%m-%d')
        target_time = target_datetime.strftime('%H:%M')
        
        cursor.execute('''
            SELECT t.user_id, t.task_text, t.task_date, t.task_time, u.first_name
            FROM tasks t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.task_date = ? AND t.task_time = ? AND t.reminded = FALSE
        ''', (target_date, target_time))
        
        tasks = cursor.fetchall()
        conn.close()
        return tasks
    
    def mark_as_reminded(self, task_ids: List[int]):
        """Пометить задачи как напомненные"""
        if not task_ids:
            return
            
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        placeholders = ','.join('?' * len(task_ids))
        cursor.execute(f'''
            UPDATE tasks SET reminded = TRUE 
            WHERE id IN ({placeholders})
        ''', task_ids)
        
        conn.commit()
        conn.close()