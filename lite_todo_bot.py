import os
import logging
import sqlite3

import telebot

from datetime import datetime
from telebot import TeleBot
from telebot.types import Message, BotCommand

lite_todo_tg_token = os.environ.get("lite_todo_tg_token")

bot = TeleBot(lite_todo_tg_token)


def init_db():
    """
    初始化SQLite数据库
    """
    conn = sqlite3.connect("todos.db")
    cursor = conn.cursor()
    cursor.execute(
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
    conn.close()


def add_todo(user_id, user_name, chat_id, task):
    """
    添加待办事项到数据库
    """
    conn = sqlite3.connect("todos.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO todos (user_id, user_name, chat_id, task, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, user_name, chat_id, task, now, now),
    )
    conn.commit()
    conn.close()


def get_todos_by_status(user_id, status=None):
    """
    获取指定状态的待办事项并按ID从大到小排序
    """
    conn = sqlite3.connect("todos.db")
    cursor = conn.cursor()

    if status is None:
        # 获取全部待办事项并按id从大到小排序
        cursor.execute(
            "SELECT id, task, status, created_at, updated_at, notes, delete_at FROM todos WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        )
    else:
        # 获取指定状态的待办事项并按id从大到小排序
        cursor.execute(
            "SELECT id, task, status, created_at, updated_at, notes, delete_at FROM todos WHERE user_id = ? AND status = ? ORDER BY id DESC",
            (user_id, status),
        )

    todos = cursor.fetchall()
    conn.close()
    return todos


def calculate_time_difference(created_at):
    """
    计算两个时间的差距
    """
    created_time = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    diff = now - created_time
    days = diff.days
    hours, remainder = divmod(diff.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{days} 天 {hours} 时 {minutes} 分"


def format_todo(task_id, task, status, created_at, updated_at, notes, delete_at):
    """
    任务显示模板
    """
    time_diff = calculate_time_difference(created_at)
    status_text = "完成 ✅" if status == 1 else "未完成 ❌"
    completed_time = f"\n完成时间：{delete_at}" if status == 1 else ""
    notes_text = f"\n备注：{notes}" if notes else ""

    return (
        f"------- 📝 {task_id} -------\n"
        f"内容：{task}\n"
        f"创建时间：{created_at}\n"
        f"距离现在：{time_diff}\n"
        f"状态：{status_text}{completed_time}{notes_text}\n"
    )


def list_tasks(message: Message, bot: TeleBot):
    """
    /list 查看未完成的待办事项
    """
    user_id = message.from_user.id
    todos = get_todos_by_status(user_id, status=0)  # 只获取未完成的任务

    if len(todos) == 0:
        bot.reply_to(message, "你没有任何未完成的待办事项。")
    else:
        tasks = "\n".join(
            [
                format_todo(
                    task_id, task, status, created_at, updated_at, notes, delete_at
                )
                for task_id, task, status, created_at, updated_at, notes, delete_at in todos
            ]
        )
        bot.reply_to(message, f"你的未完成待办事项:\n{tasks}")


def list_done_tasks(message: Message, bot: TeleBot):
    """
    /list_done - 查看已完成的待办事项
    """
    user_id = message.from_user.id
    todos = get_todos_by_status(user_id, status=1)  # 只获取已完成的任务

    if len(todos) == 0:
        bot.reply_to(message, "你没有任何已完成的待办事项。")
    else:
        tasks = "\n".join(
            [
                format_todo(
                    task_id, task, status, created_at, updated_at, notes, delete_at
                )
                for task_id, task, status, created_at, updated_at, notes, delete_at in todos
            ]
        )
        bot.reply_to(message, f"你的已完成待办事项:\n{tasks}")


def list_all_tasks(message: Message, bot: TeleBot):
    """
    /list_all - 查看所有待办事项
    """
    user_id = message.from_user.id
    todos = get_todos_by_status(user_id)  # 获取所有任务

    if len(todos) == 0:
        bot.reply_to(message, "你没有任何待办事项。")
    else:
        tasks = "\n".join(
            [
                format_todo(
                    task_id, task, status, created_at, updated_at, notes, delete_at
                )
                for task_id, task, status, created_at, updated_at, notes, delete_at in todos
            ]
        )
        bot.reply_to(message, f"你的所有待办事项:\n{tasks}")


def complete_todo(user_id, task_id):
    """
    # 删除（标记为完成）指定的待办事项
    """
    conn = sqlite3.connect("todos.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE todos SET status = 1, delete_at = ?, updated_at = ? WHERE user_id = ? AND id = ?",
        (now, now, user_id, task_id),
    )
    conn.commit()
    conn.close()


def add_note_to_task(message: Message, bot: TeleBot):
    """
    /note [任务编号] [备注内容] - 给任务添加备注
    """
    user_id = message.from_user.id
    try:
        parts = message.text.split(maxsplit=2)
        task_index = int(parts[1]) - 1
        note = parts[2]
        todos = get_todos_by_status(user_id)  # 获取所有任务

        if 0 <= task_index < len(todos):
            task_id = todos[task_index][0]
            update_task_notes(user_id, task_id, note)
            bot.reply_to(message, f"已添加备注到任务: {todos[task_index][1]}")
        else:
            bot.reply_to(message, "无效的任务编号。")
    except (IndexError, ValueError):
        bot.reply_to(message, "请提供有效的格式，如: /note 1 新的备注内容")


# 更新任务备注
def update_task_notes(user_id, task_id, notes):
    conn = sqlite3.connect("todos.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE todos SET notes = ?, updated_at = ? WHERE user_id = ? AND id = ?",
        (notes, now, user_id, task_id),
    )
    conn.commit()
    conn.close()


def edit_task(message: Message, bot: TeleBot):
    """
    /edit [任务编号] [新任务描述] - 修改任务描述
    """
    user_id = message.from_user.id
    try:
        parts = message.text.split(maxsplit=2)
        task_index = int(parts[1]) - 1
        new_task = parts[2]
        todos = get_todos_by_status(user_id)

        if 0 <= task_index < len(todos):
            task_id = todos[task_index][0]
            edit_todo(user_id, task_id, new_task)
            bot.reply_to(message, f"已修改待办事项为: {new_task}")
        else:
            bot.reply_to(message, "无效的任务编号。")
    except (IndexError, ValueError):
        bot.reply_to(message, "请提供有效的格式，如: /edit 1 新的任务描述")


def edit_todo(user_id, task_id, new_task):
    """
    修改任务内容
    """
    conn = sqlite3.connect("todos.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE todos SET task = ?, updated_at = ? WHERE user_id = ? AND id = ?",
        (new_task, now, user_id, task_id),
    )
    conn.commit()
    conn.close()


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
        "/note [任务编号] [备注内容] - 给任务添加备注\n",
    )


def add_task(message: Message, bot: TeleBot):
    """
    /add [任务] - 添加待办事项
    """
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    chat_id = message.chat.id
    try:
        task = message.text.split(maxsplit=1)[1]
        add_todo(user_id, user_name, chat_id, task)
        bot.reply_to(message, f"已添加待办事项: {task}")
    except IndexError:
        bot.reply_to(message, "请提供待办事项内容，如: /add 买牛奶")


def complete_task(message: Message, bot: TeleBot):
    """
    /complete [任务编号] - 标记任务为完成
    """
    user_id = message.from_user.id
    try:
        task_index = int(message.text.split()[1]) - 1
        todos = get_todos_by_status(user_id, status=0)  # 只允许标记未完成的任务

        if 0 <= task_index < len(todos):
            task_id = todos[task_index][0]
            complete_todo(user_id, task_id)
            bot.reply_to(message, f"已标记任务为完成: {todos[task_index][1]}")
        else:
            bot.reply_to(message, "无效的任务编号。")
    except (IndexError, ValueError):
        bot.reply_to(message, "请提供有效的格式，如: /complete 1")


def handle_all_commands(message: Message, bot: TeleBot):
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


# 运行Telegram Bot
if __name__ == "__main__":
    telebot.logger.setLevel(logging.INFO)
    init_db()

    commands = [
        ["add", "添加待办事项"],
        ["list", "查看未完成的待办事项"],
        ["list_done", "查看已完成的待办事项"],
        ["list_all", "查看所有待办事项"],
        ["edit", "修改任务描述"],
        ["complete", "标记任务为完成"],
        ["note", "给任务添加备注"],
        ["help", "帮助"],
    ]

    bot.register_message_handler(send_welcome, commands=["start"], pass_bot=True)
    bot.register_message_handler(
        handle_all_commands,
        content_types=["text"],
        commands=[cmd[0] for cmd in commands],
        pass_bot=True,
    )

    all_commands = [BotCommand(command[0], command[1]) for command in commands]

    bot.delete_my_commands()
    bot.set_my_commands(all_commands)

    bot.infinity_polling(timeout=1000, long_polling_timeout=500)
