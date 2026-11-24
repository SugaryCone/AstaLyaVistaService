from . import api

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

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

router = Router()

def format_info(task: dict) -> str:
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
            "\n"
            f"<b>Связанные задачи: ({len(task["linked_task_ids"])})</b> \n")


MAX_BUTTON_TEXT_LEN = 50
TASKS_PER_PAGE = 10
def get_tasks_keyboard(page: int, tasks: list) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="Фильтрация", callback_data="task:filter_next"),
        InlineKeyboardButton(text="Сортировка", callback_data="task:sort_next"),
    )

    total_pages = (len(tasks) + TASKS_PER_PAGE - 1) // TASKS_PER_PAGE
    if page < 1: page = 1
    if page > total_pages: page = total_pages
    
    prev_page = page - 1 if page > 1 else total_pages
    next_page = page + 1 if page < total_pages else 1
    
    pagination_row = [
        InlineKeyboardButton(text="<", callback_data=f"task:page:{prev_page}"),
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="task:set_page"),
        InlineKeyboardButton(text=">", callback_data=f"task:page:{next_page}")
    ]
    
    builder.row(*pagination_row)
    
    start_idx = (page - 1) * TASKS_PER_PAGE
    end_idx = start_idx + TASKS_PER_PAGE
    page_tasks = tasks[start_idx:end_idx]
    
    for task in page_tasks:
        description = task["description"]
        if len(description) > MAX_BUTTON_TEXT_LEN:
            description = description[:MAX_BUTTON_TEXT_LEN] + "…"
        btn_text = f"#{task["id"]} {description}"
        builder.row(InlineKeyboardButton(text=btn_text, callback_data=f"task:select:{task["id"]}"))

    builder.row(*pagination_row)
    
    return builder

@router.callback_query(F.data.startswith("task:page:"))
async def process_pagination(callback: CallbackQuery):
    logger.info("task: Page select callback")
    pass

@router.callback_query(F.data.startswith("task:select:"))
async def process_task_select(callback: CallbackQuery):
    logger.info("task: Task select callback")
    pass

@router.message(Command("task"))
async def cmd_task(message: Message) -> None:
    parts = message.text.split(" ")
    if len(parts) != 2:
        await message.answer("Использование: /task <code>номер задачи</code>")
        return
    try:
        task = api.get_task(parts[1])
        info = format_info(task)
        linked_tasks = get_tasks_keyboard(1, api.get_linked_tasks(task))
        await message.answer(text=info, reply_markup=None if len(task["linked_task_ids"]) == 0 else linked_tasks.as_markup())
    except api.APIError as exc:
        await message.answer(f"Увы и ах! {exc.status_code} \"{repr(exc)}\"")

async def register(dp: Dispatcher):
    dp.include_router(router)