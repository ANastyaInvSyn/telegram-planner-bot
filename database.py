import os
import psycopg2
from datetime import datetime
from typing import List, Tuple, Optional

print("=== ДЕБАГ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===")

# Временное хранилище в памяти
class MemoryStorage:
    def __init__(self):
        self.tasks = {}
        self.users = {}
        self.next_task_id = 1
        print("📝 Используется временное хранилище в памяти")

    def add_user(self, user_id: int, username: str, first_name: str):
        if user_id not in self.users:
            self.users[user_id] = {
                'username': username,
                'first_name': first_name,
                'registered_at': datetime.now()
            }

    def add_task(self, user_id: int, task_text: str, task_date: str, task_time: str) -> int:
        if user_id not in self.tasks:
            self.tasks[user_id] = []
        
        task_id = self.next_task_id
        self.next_task_id += 1
        
        task = {
            'id': task_id,
            'user_id': user_id,
            'text': task_text,
            'date': task_date,
            'time': task_time,
            'created_at': datetime.now(),
            'reminded': False
        }
        
        self.tasks[user_id].append(task)
        return task_id

    def get_user_tasks(self, user_id: int, date: str = None) -> List[Tuple]:
        if user_id not in self.tasks:
            return []
        
        tasks = []
        for task in self.tasks[user_id]:
            if date is None or task['date'] == date:
                if date is None:
                    tasks.append((task['id'], task['text'], task['date'], task['time']))
                else:
                    tasks.append((task['id'], task['text'], task['time']))
        
        if date is None:
            tasks.sort(key=lambda x: (x[2], x[3]))
        else:
            tasks.sort(key=lambda x: x[2])
        
        return tasks

    def delete_task(self, task_id: int, user_id: int):
        if user_id in self.tasks:
            self.tasks[user_id] = [
                task for task in self.tasks[user_id] 
                if task['id'] != task_id
            ]

    def get_tasks_for_reminder(self, target_datetime: datetime) -> List[Tuple]:
        return []

    def mark_as_reminded(self, task_ids: List[int]):
        pass

class Database:
    def __init__(self):
        print("🔍 Поиск DATABASE_URL...")
        
        # Сначала устанавливаем атрибуты по умолчанию
        self.use_postgres = False
        self.storage = MemoryStorage()
        self.conn = None
        
        # Пробуем подключиться к PostgreSQL
        self.db_url = os.environ.get('DATABASE_URL')
        
        if self.db_url:
            print(f"✅ Найдена переменная: DATABASE_URL")
            print(f"🔗 Подключаемся к PostgreSQL: {self.db_url[:50]}...")
            try:
                self.conn = psycopg2.connect(self.db_url, sslmode='require')
                self.init_db()
                print("✅ Успешно подключено к PostgreSQL")
                self.use_postgres = True
            except Exception as e:
                print(f"❌ Ошибка подключения к PostgreSQL: {e}")
                print("📝 Используем временное хранилище")
        else:
            print("❌ Не найдена переменная базы данных, используем временное хранилище")

    def init_db(self):
        """Инициализация базы данных PostgreSQL"""
        if not self.use_postgres or not self.conn:
            return
            
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
        if self.use_postgres and self.conn:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
            ''', (user_id, username, first_name))
            self.conn.commit()
            cursor.close()
        else:
            self.storage.add_user(user_id, username, first_name)

    def add_task(self, user_id: int, task_text: str, task_date: str, task_time: str) -> int:
        if self.use_postgres and self.conn:
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
        else:
            return self.storage.add_task(user_id, task_text, task_date, task_time)

    def get_user_tasks(self, user_id: int, date: str = None) -> List[Tuple]:
        if self.use_postgres and self.conn:
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
        else:
            return self.storage.get_user_tasks(user_id, date)

    def delete_task(self, task_id: int, user_id: int):
        if self.use_postgres and self.conn:
            cursor = self.conn.cursor()
            cursor.execute('''
                DELETE FROM tasks WHERE id = %s AND user_id = %s
            ''', (task_id, user_id))
            self.conn.commit()
            cursor.close()
        else:
            self.storage.delete_task(task_id, user_id)

    def get_tasks_for_reminder(self, target_datetime: datetime) -> List[Tuple]:
        if self.use_postgres and self.conn:
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
        else:
            return []

    def mark_as_reminded(self, task_ids: List[int]):
        if self.use_postgres and self.conn and task_ids:
            cursor = self.conn.cursor()
            placeholders = ','.join(['%s'] * len(task_ids))
            cursor.execute(f'''
                UPDATE tasks SET reminded = TRUE 
                WHERE id IN ({placeholders})
            ''', task_ids)
            self.conn.commit()
            cursor.close()

def get_task_ids_for_reminder(self, target_datetime: datetime) -> List[int]:
    """Получить ID задач для напоминания"""
    if self.use_postgres and self.conn:
        cursor = self.conn.cursor()
        target_date = target_datetime.strftime('%Y-%m-%d')
        target_time = target_datetime.strftime('%H:%M')
        
        cursor.execute('''
            SELECT id FROM tasks 
            WHERE task_date = %s AND task_time = %s AND reminded = FALSE
        ''', (target_date, target_time))
        
        task_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return task_ids
    else:
        return []
