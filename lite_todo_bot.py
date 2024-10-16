import logging
import os
import sqlite3
import traceback

from datetime import datetime
from typing import List

import telebot

from telebot import TeleBot
from telebot.types import Message, BotCommand


lite_todo_tg_token = os.environ.get("lite_todo_tg_token")
DATA_DIR = os.getenv("DATA_DIR", "data")


class TodoItem:
    def __init__(
        self,
        id: int = 0,
        user_id: int = 0,
        user_name: str = "",
        chat_id: int = 0,
        task: str = "",
        status: int = 0,
        note: str = "",
        created_at: str = "",
        updated_at: str = "",
        delete_at: str = "",
    ):
        self._datetime_fmt = "%Y-%m-%d %H:%M:%S"
        now_datetime = datetime.now().strftime(self._datetime_fmt)
        self.id = int(id)
        self.user_id = int(user_id)
        self.user_name = user_name
        self.chat_id = int(chat_id)
        self.task = task
        self.status = int(status)
        self.note = note
        self.created_at = created_at if created_at else now_datetime
        self.updated_at = updated_at if updated_at else now_datetime
        self.delete_at = delete_at if delete_at else ""

    @classmethod
    def from_row(cls, row):
        return cls(*row)

    def is_completed(self):
        return self.status == 1

    def time_since_creation(self):
        diff = datetime.now() - datetime.strptime(self.created_at, self._datetime_fmt)
        days = diff.days
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{days} 天 {hours} 时 {minutes} 分"

    def display(self):
        time_diff = self.time_since_creation()
        status_text = "完成 ✅" if self.is_completed() else "未完成 ❌"
        completed_time = (
            f"\n完成时间：{self.delete_at}"
            if self.is_completed()
            else f"\n距离现在：{time_diff}"
        )
        notes_text = f"\n备注：{self.note}" if self.note else ""

        return (
            f"------- 📝 {self.id} -------\n"
            f"任务内容：{self.task}\n"
            f"创建时间：{self.created_at}\n"
            f"状态：{status_text}{completed_time}{notes_text}\n"
        )


class Database:
    def __init__(self, db="todos.db"):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._db = os.path.join(DATA_DIR, db)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_name TEXT,
                chat_id INTEGER,
                task TEXT,
                status INTEGER DEFAULT 0,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT,
                delete_at TEXT
                )"""
            )
            conn.commit()

    def add_todo(self, t: TodoItem):
        with sqlite3.connect(self._db) as conn:
            s = "INSERT INTO todos (user_id, user_name, chat_id, task, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)"
            params = [
                t.user_id,
                t.user_name,
                t.chat_id,
                t.task,
                t.created_at,
                t.updated_at,
            ]
            cursor = conn.execute(s, params)
            t.id = cursor.lastrowid
            conn.commit()

    def get_todos_by_status(self, user_id, status=None) -> List[TodoItem]:
        """
        获取指定状态的待办事项并按ID从大到小排序
        """
        s = ""
        params = []

        if status is None:
            s = "SELECT * FROM todos WHERE user_id = ? ORDER BY id DESC"
            params = [user_id]
        else:
            s = "SELECT * FROM todos WHERE user_id = ? AND status = ? ORDER BY id DESC"
            params = [user_id, status]

        result = []
        with sqlite3.connect(self._db) as conn:
            cursor = conn.execute(s, params)
            r = cursor.fetchall()
            result = [TodoItem.from_row(i) for i in r]
        return result

    def get_todos_by_task_id(self, user_id, task_id=None) -> List[TodoItem]:
        """
        获取指定状态的待办事项并按ID从大到小排序
        """
        s = ""
        params = []

        if task_id is None:
            s = "SELECT * FROM todos WHERE user_id = ? ORDER BY id DESC"
            params = [user_id]
        else:
            s = "SELECT * FROM todos WHERE user_id = ? AND id = ? ORDER BY id DESC"
            params = [user_id, task_id]

        result = []
        with sqlite3.connect(self._db) as conn:
            cursor = conn.execute(s, params)
            r = cursor.fetchall()
            result = [TodoItem.from_row(i) for i in r]
        return result

    def complete_todo(self, t: TodoItem):
        """
        # 删除（标记为完成）指定的待办事项
        """
        user_id = t.user_id
        task_id = t.id
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        t.delete_at = now
        s = "UPDATE todos SET status = 1, delete_at = ?, updated_at = ? WHERE user_id = ? AND id = ?"
        params = [now, now, user_id, task_id]

        with sqlite3.connect(self._db) as conn:
            conn.execute(s, params)
            conn.commit()

    def update_task_notes(self, t: TodoItem):
        """
        更新任务备注
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        s = "UPDATE todos SET notes = ?, updated_at = ? WHERE user_id = ? AND id = ?"
        params = [t.note, now, t.user_id, t.id]
        with sqlite3.connect(self._db) as conn:
            conn.execute(s, params)
            conn.commit()

    def edit_todo(self, t: TodoItem):
        """
        修改任务内容
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        s = "UPDATE todos SET task = ?, updated_at = ? WHERE user_id = ? AND id = ?"
        params = [t.task, now, t.user_id, t.id]
        with sqlite3.connect(self._db) as conn:
            conn.execute(s, params)
            conn.commit()


db = Database()


def list_tasks(message: Message, bot: TeleBot):
    """
    /list 查看未完成的待办事项
    """
    user_id = message.from_user.id
    todos = db.get_todos_by_status(user_id, status=0)  # 只获取未完成的任务

    if len(todos) == 0:
        bot.reply_to(message, "你没有任何未完成的待办事项。")
    else:
        tasks = "\n".join([t.display() for t in todos])
        bot.reply_to(message, f"你的未完成待办事项:\n{tasks}")


def list_done_tasks(message: Message, bot: TeleBot):
    """
    /list_done - 查看已完成的待办事项
    """

    user_id = message.from_user.id
    todos = db.get_todos_by_status(user_id, status=1)  # 只获取已完成的任务

    if len(todos) == 0:
        bot.reply_to(message, "你没有任何已完成的待办事项。")
    else:
        tasks = "\n".join([t.display() for t in todos])
        bot.reply_to(message, f"你的已完成待办事项:\n{tasks}")


def list_all_tasks(message: Message, bot: TeleBot):
    """
    /list_all - 查看所有待办事项
    """

    user_id = message.from_user.id
    todos = db.get_todos_by_status(user_id)  # 获取所有任务

    if len(todos) == 0:
        bot.reply_to(message, "你没有任何待办事项。")
    else:
        tasks = "\n".join([t.display() for t in todos])
        bot.reply_to(message, f"你的所有待办事项:\n{tasks}")


def add_note_to_task(message: Message, bot: TeleBot):
    """
    /note [任务编号] [备注内容] - 给任务添加备注
    """
    try:
        user_id = message.from_user.id

        parts = message.text.split(maxsplit=2)
        task_id = int(parts[1])
        new_note = parts[2]
        todos = db.get_todos_by_task_id(user_id, task_id)  # 获取该用户的任务
        todo = next((t for t in todos if t.id == task_id), None)

        if todo is None:
            bot.reply_to(message, "无效的任务编号。")
            return

        old_note = todo.note
        todo.note = new_note
        db.update_task_notes(todo)
        old_notes_text = f"\n备注(旧): {old_note}" if old_note else ""
        bot.reply_to(message, f"已添加备注到任务: \n{todo.display()}{old_notes_text}")
    except (IndexError, ValueError):
        bot.reply_to(message, "请提供有效的格式，如: /note 1 新的备注内容")


def edit_task(message: Message, bot: TeleBot):
    """
    /edit [任务编号] [新任务描述] - 修改任务描述
    """
    try:
        user_id = message.from_user.id

        parts = message.text.split(maxsplit=2)
        task_id = int(parts[1])
        new_task = parts[2]
        todos = db.get_todos_by_task_id(user_id, task_id)
        todo = next((t for t in todos if t.id == task_id), None)
        if todo is None:
            bot.reply_to(message, "无效的任务编号。")
            return

        old_task = todo.task
        todo.task = new_task
        db.edit_todo(todo)

        old_task_text = f"\n任务内容(旧): {old_task}" if old_task else ""
        bot.reply_to(message, f"已修改待办事项: \n{todo.display()}{old_task_text}")
    except (IndexError, ValueError):
        bot.reply_to(message, "请提供有效的格式，如: /edit 1 新的任务描述")


def add_task(message: Message, bot: TeleBot):
    """
    /add [任务] - 添加待办事项
    """

    try:
        user_id = message.from_user.id
        user_name = message.from_user.full_name
        chat_id = message.chat.id
        new_todo = TodoItem(user_id=user_id, user_name=user_name, chat_id=chat_id)

        task = message.text.split(maxsplit=1)[1]
        new_todo.task = task
        db.add_todo(new_todo)
        bot.reply_to(message, f"已添加待办事项: \n{new_todo.display()}")
    except IndexError:
        bot.reply_to(message, "请提供待办事项内容，如: /add 买牛奶")


def complete_task(message: Message, bot: TeleBot):
    """
    /complete [任务编号] - 标记任务为完成
    """

    try:
        user_id = message.from_user.id
        task_id = int(message.text.split()[1])
        todos = db.get_todos_by_task_id(user_id, task_id)
        todo = next((t for t in todos if t.id == task_id), None)

        if todo is None:
            bot.reply_to(message, "无效的任务编号。")
            return
        if int(todo.status) == 1:
            bot.reply_to(message, f"任务已完成，无需重复标记: \n{todo.display()}")
            return

        todo.status = 1
        db.complete_todo(todo)
        bot.reply_to(message, f"已标记任务为完成: \n{todo.display()}")

    except (IndexError, ValueError):
        bot.reply_to(message, "请提供有效的格式，如: /complete 1")


def handle_all_commands(message: Message, bot: TeleBot):
    try:
        text = message.text.strip() if message.text else ""

        if text.startswith("/add"):
            add_task(message, bot)

        elif text.startswith("/edit"):
            edit_task(message, bot)

        elif text.startswith("/list_done"):
            list_done_tasks(message, bot)

        elif text.startswith("/list_all"):
            list_all_tasks(message, bot)

        elif text.startswith("/list"):
            list_tasks(message, bot)

        elif text.startswith("/complete"):
            complete_task(message, bot)

        elif text.startswith("/note"):
            add_note_to_task(message, bot)

        elif text.startswith("/help"):
            send_welcome(message, bot)
        else:
            bot.reply_to(message, "未知命令，请使用有效的指令，查看帮助 /help 。")
    except Exception as e:
        traceback.print_exc()
        bot.reply_to(message, "something wrong.")


def send_welcome(message: Message, bot: TeleBot):
    bot.reply_to(
        message,
        "欢迎使用 Lite ToDo Bot! 你可以使用以下命令:\n"
        "/add [任务] - 添加待办事项\n"
        "/list - 查看未完成的待办事项\n"
        "/list_done - 查看已完成的待办事项\n"
        "/list_all - 查看所有待办事项\n"
        "/edit [任务编号] [新任务描述] - 修改任务描述\n"
        "/complete [任务编号] - 标记任务为完成\n"
        "/note [任务编号] [备注内容] - 给任务添加备注\n"
        "/help 帮助\n",
    )


def set_bot_commands(bot: TeleBot, all_commands: list[BotCommand]) -> None:
    bot.delete_my_commands()
    bot.set_my_commands(all_commands)


if __name__ == "__main__":
    telebot.logger.setLevel(logging.INFO)
    bot = TeleBot(lite_todo_tg_token)

    # 0-command: str, 1-command desc: str, 2-edited: bool
    commands = [
        ["add", "添加待办事项", False],
        ["list", "查看未完成的待办事项", False],
        ["list_done", "查看已完成的待办事项", False],
        ["list_all", "查看所有待办事项", False],
        ["edit", "修改任务描述", True],
        ["complete", "标记任务为完成", True],
        ["note", "给任务添加备注", True],
        ["help", "帮助", False],
    ]

    bot.register_message_handler(
        send_welcome, commands=["start", "help"], pass_bot=True
    )

    # all commands
    bot.register_message_handler(
        handle_all_commands,
        content_types=["text"],
        commands=[cmd[0] for cmd in commands],
        pass_bot=True,
    )

    # edited commands
    bot.register_edited_message_handler(
        handle_all_commands,
        content_types=["text"],
        commands=[cmd[0] for cmd in commands if cmd[2]],
        pass_bot=True,
    )

    all_commands = [BotCommand(command[0], command[1]) for command in commands]

    set_bot_commands(bot, all_commands)

    bot.infinity_polling(timeout=1000, long_polling_timeout=500)
