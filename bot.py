# Добавьте эти импорты в начало файла
from datetime import datetime, timedelta

# Добавьте новые состояния для ConversationHandler
WAITING_WEEKLY_TASK, WAITING_WEEKLY_WEEK = range(4, 6)  # Продолжаем с предыдущих состояний

class PlannerBot:
    # ... существующий код ...
    
    def get_main_keyboard(self):
        """Основная клавиатура меню"""
        keyboard = [
            ["📝 Добавить задачу", "📋 Мои задачи"],
            ["🗑 Удалить задачу", "📅 Сегодня"],
            ["📆 Завтра", "🗓 Недельные задачи"],
            ["ℹ️ Помощь"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_weekly_keyboard(self):
        """Клавиатура для недельных задач"""
        keyboard = [
            ["📋 Мои недельные задачи", "➕ Добавить недельную задачу"],
            ["⬅️ Назад"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_week_choice_keyboard(self):
        """Выбор недели для добавления задачи"""
        today = datetime.now().date()
        current_week_start = self._get_week_start(today)
        next_week_start = current_week_start + timedelta(days=7)
        
        keyboard = [
            [f"📅 Текущая неделя ({current_week_start.strftime('%d.%m')})"],
            [f"📅 Следующая неделя ({next_week_start.strftime('%d.%m')})"],
            ["❌ Отмена"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def _get_week_start(self, date):
        """Получить дату начала недели (понедельник)"""
        return date - timedelta(days=date.weekday())
    
    # Добавьте новые обработчики в setup_handlers
    def setup_handlers(self):
        # ... существующие обработчики ...
        
        # Обработчики для недельных задач
        self.application.add_handler(MessageHandler(filters.Text("🗓 Недельные задачи"), self.weekly_tasks_menu))
        self.application.add_handler(MessageHandler(filters.Text("📋 Мои недельные задачи"), self.show_weekly_tasks))
        self.application.add_handler(MessageHandler(filters.Text("➕ Добавить недельную задачу"), self.start_add_weekly_task))
        
        # ConversationHandler для добавления недельных задач
        weekly_conv_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Text("➕ Добавить недельную задачу"), self.start_add_weekly_task)
            ],
            states={
                WAITING_WEEKLY_TASK: [
                    MessageHandler(filters.TEXT & ~filters.Text(["❌ Отмена", "⬅️ Назад"]), self.get_weekly_task_text)
                ],
                WAITING_WEEKLY_WEEK: [
                    MessageHandler(filters.TEXT & ~filters.Text(["❌ Отмена", "⬅️ Назад"]), self.get_weekly_task_week)
                ],
            },
            fallbacks=[
                MessageHandler(filters.Text("❌ Отмена"), self.cancel_command),
                MessageHandler(filters.Text("⬅️ Назад"), self.back_to_main)
            ],
        )
        self.application.add_handler(weekly_conv_handler)
        
        # Обработчик для отметки выполнения недельных задач
        self.application.add_handler(MessageHandler(filters.Regex(r'^✓ Выполнить_\d+$'), self.complete_weekly_task))
    
    # Новые методы для недельных задач
    
    async def weekly_tasks_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Меню недельных задач"""
        await update.message.reply_text(
            "🗓 Управление недельными задачами:\n\n"
            "• Задачи без конкретного времени\n"
            "• Напоминания каждый день в 10:00\n"
            "• Автоперенос на следующую неделю",
            reply_markup=self.get_weekly_keyboard()
        )
    
    async def start_add_weekly_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало добавления недельной задачи"""
        context.user_data.clear()
        
        await update.message.reply_text(
            "📝 Введите описание недельной задачи:",
            reply_markup=self.get_cancel_keyboard()
        )
        return WAITING_WEEKLY_TASK
    
    async def get_weekly_task_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение текста недельной задачи"""
        task_text = update.message.text.strip()
        if not task_text:
            await update.message.reply_text("❌ Описание не может быть пустым!")
            return WAITING_WEEKLY_TASK
        
        context.user_data['weekly_task_text'] = task_text
        
        today = datetime.now().date()
        current_week_start = self._get_week_start(today)
        next_week_start = current_week_start + timedelta(days=7)
        
        await update.message.reply_text(
            f"📅 Выберите неделю для задачи:\n\n"
            f"• Текущая: {current_week_start.strftime('%d.%m')} - {(current_week_start + timedelta(days=6)).strftime('%d.%m.%Y')}\n"
            f"• Следующая: {next_week_start.strftime('%d.%m')} - {(next_week_start + timedelta(days=6)).strftime('%d.%m.%Y')}",
            reply_markup=self.get_week_choice_keyboard()
        )
        return WAITING_WEEKLY_WEEK
    
    async def get_weekly_task_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение выбора недели и сохранение задачи"""
        week_choice = update.message.text
        user_id = update.effective_user.id
        task_text = context.user_data['weekly_task_text']
        
        today = datetime.now().date()
        
        if "Текущая неделя" in week_choice:
            week_start = self._get_week_start(today)
        elif "Следующая неделя" in week_choice:
            week_start = self._get_week_start(today) + timedelta(days=7)
        else:
            await update.message.reply_text("❌ Неверный выбор недели!")
            return WAITING_WEEKLY_WEEK
        
        # Сохраняем задачу
        task_id = self.db.add_weekly_task(user_id, task_text, week_start.strftime("%Y-%m-%d"))
        
        week_end = week_start + timedelta(days=6)
        success_text = (
            f"✅ Недельная задача добавлена!\n\n"
            f"📝 {task_text}\n"
            f"📅 Неделя: {week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m.%Y')}\n\n"
            f"Я буду напоминать о ней каждый день в 10:00! ⏰"
        )
        
        await update.message.reply_text(
            success_text,
            reply_markup=self.get_main_keyboard()
        )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def show_weekly_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать недельные задачи пользователя"""
        user_id = update.effective_user.id
        today = datetime.now().date()
        current_week_start = self._get_week_start(today)
        
        tasks = self.db.get_weekly_tasks(user_id, current_week_start.strftime("%Y-%m-%d"))
        
        if not tasks:
            await update.message.reply_text(
                "📭 На эту неделю задач нет!",
                reply_markup=self.get_weekly_keyboard()
            )
            return
        
        week_end = current_week_start + timedelta(days=6)
        tasks_text = f"🗓 Задачи на неделю ({current_week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m.%Y')}):\n\n"
        
        completed_count = 0
        for task_id, task_text, completed in tasks:
            if completed:
                tasks_text += f"✅ {task_text}\n"
                completed_count += 1
            else:
                tasks_text += f"📝 {task_text}\n"
                tasks_text += f"   ✓ Выполнить_{task_id}\n\n"
        
        total_count = len(tasks)
        tasks_text += f"\n📊 Прогресс: {completed_count}/{total_count} выполнено"
        
        if completed_count == total_count:
            tasks_text += "\n\n🎉 Все задачи выполнены! Отличная работа!"
        
        await update.message.reply_text(
            tasks_text,
            reply_markup=self.get_weekly_keyboard()
        )
    
    async def complete_weekly_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отметить недельную задачу как выполненную"""
        user_id = update.effective_user.id
        button_text = update.message.text
        task_id = int(button_text.split('_')[1])
        
        self.db.complete_weekly_task(task_id, user_id)
        
        await update.message.reply_text(
            f"✅ Задача отмечена как выполненная!",
            reply_markup=self.get_weekly_keyboard()
        )
    
    # Обновите help_command
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "📖 Помощь по использованию бота:\n\n"
            "🔸 📝 Добавить задачу - задача с конкретным временем\n"
            "🔸 📋 Мои задачи - все запланированные задачи\n"
            "🔸 🗑 Удалить задачу - удалить задачу по ID\n"
            "🔸 📅 Сегодня - задачи на сегодня\n"
            "🔸 📆 Завтра - задачи на завтра\n"
            "🔸 🗓 Недельные задачи - задачи на всю неделю\n\n"
            "🗓 Недельные задачи:\n"
            "• Без конкретного времени\n"
            "• Напоминания каждый день в 10:00\n"
            "• Автоперенос на следующую неделю\n"
            "• Можно добавить на текущую или следующую неделю\n\n"
            "❌ Отмена - отменить текущее действие\n"
            "⬅️ Назад - вернуться в меню"
        )
        await update.message.reply_text(help_text, reply_markup=self.get_main_keyboard())
