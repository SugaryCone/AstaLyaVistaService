from . import api

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger
import requests

TASK_TYPE = {
    "task": "Задача",
    "bug": "Ошибка",
    "requirement": "Требование",
}

TASK_STATUS = {
    "registered": "Зарегистрирован",
    "in_progress": "В реализации",
    "in_review": "На проверке",
    "rework": "На исправлении ошибок",
    "closed": "Закрыт",
}

def format_info(task_id: str) -> str:
    try:
        task = api.get_task(task_id)

        try:
            project_name = api.get_search_project(task["project_id"])["name"]
        except api.APIError:
            project_name = "<i>Без названия</i>"
        
        try:
            employee_name = f"<a href=\"https://t.me/{task["assignee_id"]}\">{api.get_search_employee(task["assignee_id"])["name"]}</a>"
        except api.APIError:
            employee_name = "<i>Не установлен</i>"

        return (f"<b>Задача:</b> {task["id"]} ({task["number"]})\n"
                f"<b>Статус:</b> {TASK_STATUS[task["status"]]}\n"
                f"<b>Тип:</b> {TASK_TYPE[task["type"]]}\n"
                f"<b>Проект:</b> {project_name}\n"
                f"<b>Исполнитель:</b> {employee_name}\n"
                "\n"
                f"<b>Описание:</b> {task["description"]}\n"
                "\n"
                f"<b>Открыта:</b> {"да" if task["is_open"] else "нет"}\n"
                f"<b>Просрочена:</b> {"да" if task["is_overdue"] else "нет"}\n"
                f"<b>Времени затрачено (мин):</b> {task["spent_minutes"]}\n"
                f"<b>Выполнить до:</b> {task["due_date"]}\n"
                f"<b>Связанные задачи:</b> TODO:\n")
    except:
        raise

async def cmd_task(message: Message) -> None:
    parts = message.text.split(" ")
    if len(parts) != 2:
        await message.answer("Использование: /task <code>номер задачи</code>")
        return
    try:
        info = format_info(parts[1])
        await message.answer(info)
    except api.APIError as exc:
        await message.answer(f"Увы и ах! {exc.status_code} \"{repr(exc)}\"")

async def register(dp: Dispatcher):
    logger.info("\"/task\" command registered")
    dp.message.register(cmd_task, Command("task"))
    # dp.include_router(router)