import logging
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, ConversationHandler, filters
)
from datetime import datetime, timedelta
import re

from config import BOT_TOKEN, TIMEZONE, REMINDER_TIMES
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
            ["📆 Завтра", "ℹ️ Помощь"]
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
        
        # Обработчик для добавления задач через ConversationHandler
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
        
        # Обработчики для кнопок главного меню
        main_menu_handlers = [
            MessageHandler(filters.Text("📋 Мои задачи"), self.all_tasks_button),
            MessageHandler(filters.Text("📅 Сегодня"), self.today_tasks_button),
            MessageHandler(filters.Text("📆 Завтра"), self.tomorrow_tasks_button),
            MessageHandler(filters.Text("ℹ️ Помощь"), self.help_button),
            MessageHandler(filters.Text("🗑 Удалить задачу"), self.delete_task_button),
            MessageHandler(filters.Text("⬅️ Назад"), self.back_to_main)
        ]
        
        for handler in main_menu_handlers:
            self.application.add_handler(handler)
        
        # Обработчик для удаления задач через кнопки
        self.application.add_handler(MessageHandler(filters.Regex(r'^🗑 Удалить_\d+$'), self.quick_delete_task))
        
        # Обработчик для удаления по ID
        self.application.add_handler(MessageHandler(filters.Regex(r'^\d+$'), self.delete_by_id))
        
        # Обработчик неизвестных команд
        self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown_command))
        
        # Обработчик любых текстовых сообщений
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
            f"• ℹ️ Помощь - инструкция по использованию"
        )
        
        await update.message.reply_text(
            welcome_text, 
            reply_markup=self.get_main_keyboard()
        )
    
    async def start_add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса добавления задачи"""
        logger.info(f"Начало добавления задачи для пользователя {update.effective_user.id}")
        
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
        
        if date_text == "📅 Сегодня":
            task_date = datetime.now().date()
        elif date_text == "📆 Завтра":
            task_date = (datetime.now() + timedelta(days=1)).date()
        elif date_text == "🗓 Послезавтра":
            task_date = (datetime.now() + timedelta(days=2)).date()
        else:
            try:
                task_date = datetime.strptime(date_text, "%d.%m.%Y").date()
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат даты! Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например: 25.12.2024) или выберите из кнопок:",
                    reply_markup=self.get_quick_dates_keyboard()
                )
                return WAITING_DATE
        
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
        
        if time_text == "⏰ Сейчас":
            now = datetime.now() + timedelta(minutes=1)
            task_time = now.strftime("%H:%M")
        elif time_text == "🕐 Через 1 час":
            task_time = (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
        elif time_text == "🕑 Через 2 часа":
            task_time = (datetime.now() + timedelta(hours=2)).strftime("%H:%M")
        else:
            if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time_text):
                await update.message.reply_text(
                    "❌ Неверный формат времени! Пожалуйста, введите время в формате ЧЧ:ММ (например: 14:30) или выберите из кнопок:",
                    reply_markup=self.get_time_keyboard()
                )
                return WAITING_TIME
            task_time = time_text
        
        user_id = update.effective_user.id
        task_text = context.user_data['task_text']
        task_date = context.user_data['task_date']
        display_date = context.user_data['display_date']
        
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
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def delete_task_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки удаления задачи"""
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
        
        user_tasks = self.db.get_user_tasks(user_id)
        task_exists = any(task[0] == task_id for task in user_tasks)
        
        if not task_exists:
            await update.message.reply_text(
                f"❌ Задача с ID {task_id} не найдена или не принадлежит вам!",
                reply_markup=self.get_back_keyboard()
            )
            return
        
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
    
    async def help_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Помощь'"""
        await self.help_command(update, context)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "📖 Помощь по использованию бота:\n\n"
            "🔸 📝 Добавить задачу - создать новое напоминание\n"
            "🔸 📋 Мои задачи - посмотреть все ваши задачи\n"
            "🔸 🗑 Удалить задачу - удалить задачу по ID\n"
            "🔸 📅 Сегодня - задачи на сегодня\n"
            "🔸 📆 Завтра - задачи на завтра\n\n"
            "💡 Как добавить задачу:\n"
            "1. Нажмите '📝 Добавить задачу'\n"
            "2. Введите описание задачи\n"
            "3. Выберите дату (или введите)\n"
            "4. Выберите время (или введите)\n\n"
            "💡 Как удалить задачу:\n"
            "• Способ 1: Нажмите '🗑 Удалить задачу' и введите ID задачи\n"
            "• Способ 2: В списке задач нажмите кнопку '🗑 Удалить_X'\n\n"
            "⏰ Бот автоматически напомнит о задаче за 5, 15, 30 и 60 минут!\n\n"
            "❌ Чтобы отменить действие - нажмите '❌ Отмена'\n"
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
        if context.user_data:
            return
            
        await update.message.reply_text(
            "Используйте кнопки меню для управления задачами:",
            reply_markup=self.get_main_keyboard()
        )
    
    def run(self):
        """Запуск бота"""
        print("🚀 Запуск Telegram бота...")
        self.db.check_database_status()
        
        self.setup_handlers()
        
        self.scheduler = Scheduler(self.application.bot)
        self.scheduler.start()
        
        print("✅ Бот запущен! Нажмите Ctrl+C для остановки.")
        
        self.application.run_polling()
        
        if self.scheduler:
            self.scheduler.stop()

if __name__ == "__main__":
    bot = PlannerBot()
    bot.run()
