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
                if self.init_db():  # ← Теперь проверяем результат инициализации
                    print("✅ Успешно подключено к PostgreSQL")
                    self.use_postgres = True
                else:
                    print("❌ Не удалось инициализировать базу данных")
                    self.use_postgres = False
            except Exception as e:
                print(f"❌ Ошибка подключения к PostgreSQL: {e}")
                print("📝 Используем временное хранилище")
        else:
            print("❌ Не найдена переменная базы данных, используем временное хранилище")

    def init_db(self):
        """Инициализация базы данных PostgreSQL"""
        if not self.conn:
            return False
            
        cursor = self.conn.cursor()
        
        try:
            print("🔄 Проверка и создание таблиц...")
            
            # Создаем таблицу users
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Создаем таблицу tasks
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
            
            self.conn.commit()
            print("✅ Таблицы успешно созданы или уже существуют")
            
            # Проверяем создание таблиц
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('users', 'tasks')
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
            print(f"✅ Существующие таблицы: {existing_tables}")
            
            cursor.close()
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при создании таблиц: {e}")
            self.conn.rollback()
            cursor.close()
            return False
