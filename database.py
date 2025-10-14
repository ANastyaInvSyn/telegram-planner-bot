import os
from datetime import datetime
from typing import List, Tuple, Optional

print("=== ДЕБАГ: Запуск database.py ===")
print(f"DATABASE_URL в окружении: {'DATABASE_URL' in os.environ}")

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
        
        # Сортировка
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
        # Временно отключаем напоминания
        return []

    def mark_as_reminded(self, task_ids: List[int]):
        pass

class Database:
    def __init__(self):
        self.storage = MemoryStorage()
        print("✅ База данных инициализирована (MemoryStorage)")

    def init_db(self):
        pass

    def add_user(self, user_id: int, username: str, first_name: str):
        self.storage.add_user(user_id, username, first_name)

    def add_task(self, user_id: int, task_text: str, task_date: str, task_time: str) -> int:
        return self.storage.add_task(user_id, task_text, task_date, task_time)

    def get_user_tasks(self, user_id: int, date: str = None) -> List[Tuple]:
        return self.storage.get_user_tasks(user_id, date)

    def delete_task(self, task_id: int, user_id: int):
        self.storage.delete_task(task_id, user_id)

    def get_tasks_for_reminder(self, target_datetime: datetime) -> List[Tuple]:
        return self.storage.get_tasks_for_reminder(target_datetime)

    def mark_as_reminded(self, task_ids: List[int]):
        self.storage.mark_as_reminded(task_ids)
