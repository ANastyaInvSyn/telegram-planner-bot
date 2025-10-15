import logging
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, ConversationHandler, filters
)
from datetime import datetime, timedelta
import re

from config import BOT_TOKEN
from database import Database
from scheduler import Scheduler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_TASK, WAITING_DATE, WAITING_TIME = range(3)
WAITING_WEEKLY_TASK, WAITING_WEEKLY_WEEK = range(4, 6)

class PlannerBot:
    def __init__(self):
        self.db = Database()
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.scheduler = None
        
    def get_main_keyboard(self):
        """Основная клавиатура меню"""
        keyboard = [
            ["📝 Добавить задачу", "📋 Мои задачи"],
            ["🗑 Удалить задачу", "📅 Сегодня"],
            ["📆 Завтра", "🗓 Недельные задачи"],
            ["ℹ️ Помощь"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_cancel_keyboard(self):
        """Клавиатура для отмены"""
        return ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
    
    def get_quick_dates_keyboard(self):
        """Быстрый выбор дат"""
        keyboard = [
            ["📅 Сегодня", "📆 Завтра"],
            ["🗓 Послезавтра", "❌ Отмена"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_time_keyboard(self):
        """Быстрый выбор времени"""
        keyboard = [
            ["⏰ Сейчас", "🕐 Через 1 час"],
            ["🕑 Через 2 часа", "❌ Отмена"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_back_keyboard(self):
        """Клавиатура с кнопкой Назад"""
        return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
    
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
    
    def get_tasks_with_delete_buttons(self, tasks):
        """Формирует список задач с кнопками удаления"""
        if not tasks:
            return "📭 Задач нет!"
        
        tasks_text = ""
        for task in tasks:
            if len(task) == 4:  # Все задачи (id, text, date, time)
                task_id, task_text, task_date, task_time = task
                display_date = datetime.strptime(task_date, "%Y-%m-%d").strftime("%d.%m.%Y")
                tasks_text += f"🆔 {task_id}: {task_text}\n"
                tasks_text += f"   📅 {display_date} 🕐 {task_time}\n"
                tasks_text += f"   🗑 Удалить_{task_id}\n\n"
            else:  # Задачи на сегодня/завтра (id, text, time)
                task_id, task_text, task_time = task
                tasks_text += f"🆔 {task_id}: {task_text}\n"
                tasks_text += f"   🕐 {task_time}\n"
                tasks_text += f"   🗑 Удалить_{task_id}\n\n"
        
        return tasks_text
        
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        
        # Обработчики команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("tasks", self.all_tasks_command))
        self.application.add_handler(CommandHandler("today", self.today_tasks_command))
        self.application.add_handler(CommandHandler("tomorrow", self.tomorrow_tasks_command))
        self.application.add_handler(CommandHandler("delete", self.delete_command))
        
        # Обработчик для добавления ежедневных задач через ConversationHandler
        add_conv_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Text("📝 Добавить задачу"), self.start_add_task),
                CommandHandler("add", self.start_add_task)
            ],
            states={
                WAITING_TASK: [
                    MessageHandler(filters.TEXT & ~filters.Text(["❌ Отмена", "⬅️ Назад"]), self.get_task_text)
                ],
                WAITING_DATE: [
                    MessageHandler(filters.TEXT & ~filters.Text(["❌ Отмена", "⬅️ Назад"]), self.get_task_date)
                ],
                WAITING_TIME: [
                    MessageHandler(filters.TEXT & ~filters.Text(["❌ Отмена", "⬅️ Назад"]), self.get_task_time)
                ],
            },
            fallbacks=[
                MessageHandler(filters.Text("❌ Отмена"), self.cancel_command),
                CommandHandler("cancel", self.cancel_command),
                MessageHandler(filters.Text("⬅️ Назад"), self.back_to_main)
            ],
        )
        self.application.add_handler(add_conv_handler)
        
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
        
        # Обработчики для кнопок главного меню
        main_menu_handlers = [
            MessageHandler(filters.Text("📋 Мои задачи"), self.all_tasks_button),
            MessageHandler(filters.Text("📅 Сегодня"), self.today_tasks_button),
            MessageHandler(filters.Text("📆 Завтра"), self.tomorrow_tasks_button),
            MessageHandler(filters.Text("ℹ️ Помощь"), self.help_button),
            MessageHandler(filters.Text("🗑 Удалить задачу"), self.delete_task_button),
            MessageHandler(filters.Text("⬅️ Назад"), self.back_to_main),
            MessageHandler(filters.Text("🗓 Недельные задачи"), self.weekly_tasks_menu),
            MessageHandler(filters.Text("📋 Мои недельные задачи"), self.show_weekly_tasks),
            MessageHandler(filters.Text("➕ Добавить недельную задачу"), self.start_add_weekly_task)
        ]
        
        for handler in main_menu_handlers:
            self.application.add_handler(handler)
        
        # Обработчик для удаления задач через кнопки
        self.application.add_handler(MessageHandler(filters.Regex(r'^🗑 Удалить_\d+$'), self.quick_delete_task))
        
        # Обработчик для отметки выполнения недельных задач
        self.application.add_handler(MessageHandler(filters.Regex(r'^✓ Выполнить_\d+$'), self.complete_weekly_task))
        
        # Обработчик для удаления по ID (простой текст)
        self.application.add_handler(MessageHandler(filters.Regex(r'^\d+$'), self.delete_by_id))
        
        # Обработчик неизвестных команд
        self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown_command))
        
        # Обработчик любых текстовых сообщений (если не попали в другие обработчики)
        self.application.add_handler(MessageHandler(filters.TEXT, self.handle_any_text))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        self.db.add_user(user.id, user.username, user.first_name)
        
        welcome_text = (
            f"Привет, {user.first_name}! 👋\n"
            f"Я твой персональный ежедневник!\n\n"
            f"📋 Используй кнопки ниже для управления задачами:\n\n"
            f"• 📝 Добавить задачу - создать новое напоминание\n"
            f"• 📋 Мои задачи - посмотреть все задачи\n"
            f"• 🗑 Удалить задачу - удалить задачу по ID\n"
            f"• 📅 Сегодня - задачи на сегодня\n"
            f"• 📆 Завтра - задачи на завтра\n"
            f"• 🗓 Недельные задачи - задачи на всю неделю\n"
            f"• ℹ️ Помощь - инструкция по использованию"
        )
        
        await update.message.reply_text(
            welcome_text, 
            reply_markup=self.get_main_keyboard()
        )
    
    async def start_add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса добавления задачи"""
        logger.info(f"Начало добавления задачи для пользователя {update.effective_user.id}")
        
        # Очищаем предыдущие данные
        context.user_data.clear()
        
        await update.message.reply_text(
            "📝 Введите описание вашей задачи:",
            reply_markup=self.get_cancel_keyboard()
        )
        return WAITING_TASK
    
    async def get_task_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение текста задачи"""
        task_text = update.message.text.strip()
        if not task_text:
            await update.message.reply_text(
                "❌ Описание задачи не может быть пустым! Введите описание:",
                reply_markup=self.get_cancel_keyboard()
            )
            return WAITING_TASK
        
        # Проверяем, что это не время (формат ЧЧ:ММ)
        time_pattern = r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'
        if re.match(time_pattern, task_text):
            await update.message.reply_text(
                "❌ Вы ввели время вместо описания задачи! Пожалуйста, введите текстовое описание задачи:",
                reply_markup=self.get_cancel_keyboard()
            )
            return WAITING_TASK
        
        context.user_data['task_text'] = task_text
        
        await update.message.reply_text(
            "📅 Выберите дату задачи или введите в формате ДД.ММ.ГГГГ:",
            reply_markup=self.get_quick_dates_keyboard()
        )
        return WAITING_DATE
    
    async def get_task_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение даты задачи"""
        date_text = update.message.text
        
        # Обработка быстрого выбора дат
        if date_text == "📅 Сегодня":
            task_date = datetime.now().date()
        elif date_text == "📆 Завтра":
            task_date = (datetime.now() + timedelta(days=1)).date()
        elif date_text == "🗓 Послезавтра":
            task_date = (datetime.now() + timedelta(days=2)).date()
        else:
            # Парсим введенную дату
            try:
                task_date = datetime.strptime(date_text, "%d.%m.%Y").date()
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат даты! Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например: 25.12.2024) или выберите из кнопок:",
                    reply_markup=self.get_quick_dates_keyboard()
                )
                return WAITING_DATE
        
        # Проверяем, что дата не в прошлом
        if task_date < datetime.now().date():
            await update.message.reply_text(
                "❌ Нельзя добавлять задачи на прошедшие даты! Выберите другую дату:",
                reply_markup=self.get_quick_dates_keyboard()
            )
            return WAITING_DATE
        
        context.user_data['task_date'] = task_date.strftime("%Y-%m-%d")
        context.user_data['display_date'] = task_date.strftime("%d.%m.%Y")
        
        await update.message.reply_text(
            "🕐 Выберите время или введите в формате ЧЧ:ММ:",
            reply_markup=self.get_time_keyboard()
        )
        return WAITING_TIME
    
    async def get_task_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение времени задачи и сохранение"""
        time_text = update.message.text
        
        # Обработка быстрого выбора времени
        if time_text == "⏰ Сейчас":
            now = datetime.now() + timedelta(minutes=1)
            task_time = now.strftime("%H:%M")
        elif time_text == "🕐 Через 1 час":
            task_time = (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
        elif time_text == "🕑 Через 2 часа":
            task_time = (datetime.now() + timedelta(hours=2)).strftime("%H:%M")
        else:
            # Парсим введенное время
            if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time_text):
                await update.message.reply_text(
                    "❌ Неверный формат времени! Пожалуйста, введите время в формате ЧЧ:ММ (например: 14:30) или выберите из кнопок:",
                    reply_markup=self.get_time_keyboard()
                )
                return WAITING_TIME
            task_time = time_text
        
        # Получаем данные из контекста
        user_id = update.effective_user.id
        task_text = context.user_data['task_text']
        task_date = context.user_data['task_date']
        display_date = context.user_data['display_date']
        
        # Сохраняем задачу в базу
        task_id = self.db.add_task(user_id, task_text, task_date, task_time)
        
        success_text = (
            f"✅ Задача успешно добавлена!\n\n"
            f"📝 {task_text}\n"
            f"📅 {display_date}\n"
            f"🕐 {task_time}\n\n"
            f"ID задачи: {task_id}\n"
            f"Я напомню о задаче заранее! 🔔"
        )
        
        await update.message.reply_text(
            success_text, 
            reply_markup=self.get_main_keyboard()
        )
        
        # Очищаем user_data
        context.user_data.clear()
        
        logger.info(f"Задача {task_id} добавлена для пользователя {user_id}")
        return ConversationHandler.END
    
    async def delete_task_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки удаления задачи - показывает список для удаления по ID"""
        user_id = update.effective_user.id
        tasks = self.db.get_user_tasks(user_id)
        
        if not tasks:
            await update.message.reply_text(
                "📭 У вас пока нет задач для удаления!",
                reply_markup=self.get_main_keyboard()
            )
            return
        
        tasks_text = "🗑 Выберите задачу для удаления:\n\n"
        tasks_text += self.get_tasks_with_delete_buttons(tasks)
        tasks_text += "\n📝 Или введите ID задачи для удаления:"
        
        await update.message.reply_text(
            tasks_text,
            reply_markup=self.get_back_keyboard()
        )
    
    async def delete_by_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаление задачи по введенному ID"""
        # Проверяем, не находимся ли мы в состоянии добавления задачи
        if context.user_data:
            await update.message.reply_text(
                "❌ Сначала завершите добавление задачи или нажмите '❌ Отмена'",
                reply_markup=self.get_cancel_keyboard()
            )
            return
        
        user_id = update.effective_user.id
        task_id_text = update.message.text
        
        try:
            task_id = int(task_id_text)
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат ID! Введите число (ID задачи):",
                reply_markup=self.get_back_keyboard()
            )
            return
        
        # Проверяем, существует ли задача у этого пользователя
        user_tasks = self.db.get_user_tasks(user_id)
        task_exists = any(task[0] == task_id for task in user_tasks)
        
        if not task_exists:
            await update.message.reply_text(
                f"❌ Задача с ID {task_id} не найдена или не принадлежит вам!",
                reply_markup=self.get_back_keyboard()
            )
            return
        
        # Удаляем задачу
        self.db.delete_task(task_id, user_id)
        
        await update.message.reply_text(
            f"✅ Задача с ID {task_id} успешно удалена!",
            reply_markup=self.get_main_keyboard()
        )
    
    async def quick_delete_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Быстрое удаление задачи через кнопку в списке"""
        user_id = update.effective_user.id
        button_text = update.message.text
        task_id = int(button_text.split('_')[1])
        
        # Удаляем задачу
        self.db.delete_task(task_id, user_id)
        
        await update.message.reply_text(
            f"✅ Задача с ID {task_id} успешно удалена!",
            reply_markup=self.get_main_keyboard()
        )
    
    async def delete_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /delete"""
        await self.delete_task_button(update, context)
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена добавления задачи"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Действие отменено.",
            reply_markup=self.get_main_keyboard()
        )
        return ConversationHandler.END
    
    async def back_to_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат в главное меню"""
        # Если мы в процессе добавления задачи, очищаем состояние
        if context.user_data:
            context.user_data.clear()
        
        await update.message.reply_text(
            "⬅️ Возврат в главное меню",
            reply_markup=self.get_main_keyboard()
        )
        return ConversationHandler.END
    
    async def all_tasks_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все задачи пользователя через кнопку"""
        await self.all_tasks_command(update, context)
    
    async def all_tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все задачи пользователя"""
        user_id = update.effective_user.id
        tasks = self.db.get_user_tasks(user_id)
        
        if not tasks:
            await update.message.reply_text(
                "📭 У вас пока нет задач!",
                reply_markup=self.get_main_keyboard()
            )
            return
        
        tasks_text = "📋 Все ваши задачи:\n\n"
        tasks_text += self.get_tasks_with_delete_buttons(tasks)
        
        await update.message.reply_text(tasks_text, reply_markup=self.get_main_keyboard())
    
    async def today_tasks_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать задачи на сегодня через кнопку"""
        await self.today_tasks_command(update, context)
    
    async def today_tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать задачи на сегодня"""
        user_id = update.effective_user.id
        today = datetime.now().strftime("%Y-%m-%d")
        tasks = self.db.get_user_tasks(user_id, today)
        
        if not tasks:
            await update.message.reply_text(
                "🎉 На сегодня задач нет! Можете отдыхать!",
                reply_markup=self.get_main_keyboard()
            )
            return
        
        tasks_text = "📅 Задачи на сегодня:\n\n"
        tasks_text += self.get_tasks_with_delete_buttons(tasks)
        
        await update.message.reply_text(tasks_text, reply_markup=self.get_main_keyboard())
    
    async def tomorrow_tasks_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать задачи на завтра через кнопку"""
        await self.tomorrow_tasks_command(update, context)
    
    async def tomorrow_tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать задачи на завтра"""
        user_id = update.effective_user.id
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        tasks = self.db.get_user_tasks(user_id, tomorrow)
        
        if not tasks:
            await update.message.reply_text(
                "📭 На завтра задач пока нет!",
                reply_markup=self.get_main_keyboard()
            )
            return
        
        tasks_text = "📆 Задачи на завтра:\n\n"
        tasks_text += self.get_tasks_with_delete_buttons(tasks)
        
        await update.message.reply_text(tasks_text, reply_markup=self.get_main_keyboard())
    
    # === МЕТОДЫ ДЛЯ НЕДЕЛЬНЫХ ЗАДАЧ ===
    
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
    
    async def help_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Помощь'"""
        await self.help_command(update, context)
    
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
            "⬅️ Чтобы вернуться в меню - нажмите '⬅️ Назад'"
        )
        await update.message.reply_text(help_text, reply_markup=self.get_main_keyboard())
    
    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик неизвестных команд"""
        await update.message.reply_text(
            "❌ Неизвестная команда. Используйте кнопки меню для управления задачами.",
            reply_markup=self.get_main_keyboard()
        )
    
    async def handle_any_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик любых текстовых сообщений"""
        # Если есть активное состояние, игнорируем это сообщение
        # ConversationHandler сам обработает его
        if context.user_data:
            return
            
        await update.message.reply_text(
            "Используйте кнопки меню для управления задачами:",
            reply_markup=self.get_main_keyboard()
        )
    
    def run(self):
        """Запуск бота"""
        print("🚀 Запуск Telegram бота...")
        self.setup_handlers()
        
        # Запускаем планировщик напоминаний
        self.scheduler = Scheduler(self.application.bot)
        self.scheduler.start()
        
        print("✅ Бот запущен! Нажмите Ctrl+C для остановки.")
        
        # Запускаем бота
        self.application.run_polling()
        
        # При остановке останавливаем планировщик
        if self.scheduler:
            self.scheduler.stop()

if __name__ == "__main__":
    bot = PlannerBot()
    bot.run()

