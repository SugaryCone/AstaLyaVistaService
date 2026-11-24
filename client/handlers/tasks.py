from . import api
from os import getenv

import math
from loguru import logger
from aiogram import Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

MAX_BUTTON_TEXT_LEN = 50
TASKS_PER_PAGE = 10
# API_URL = getenv("CLIENT_API_URL")

def get_tasks_keyboard(page: int, tasks: list) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="Фильтрация", callback_data="filter_next"),
        InlineKeyboardButton(text="Сортировка", callback_data="sort_next"),
    )

    total_pages = (len(tasks) + TASKS_PER_PAGE - 1) // TASKS_PER_PAGE
    if page < 1: page = 1
    if page > total_pages: page = total_pages
    
    prev_page = page - 1 if page > 1 else total_pages
    next_page = page + 1 if page < total_pages else 1
    
    pagination_row = [
        InlineKeyboardButton(text="<", callback_data=f"tasks_page:{prev_page}"),
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="tasks_set_page"),
        InlineKeyboardButton(text=">", callback_data=f"tasks_page:{next_page}")
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
        builder.row(InlineKeyboardButton(text=btn_text, callback_data=f"task_click:{task['id']}"))
        
    builder.row(*pagination_row)
    
    return builder


@router.message(Command("tasks"))
async def cmd_tasks(message: Message):
    tasks = api.get_tasks()
    total_count = len(tasks)
    kb_builder = get_tasks_keyboard(page=1, tasks=tasks)
    
    await message.answer(
        text=f"Всего {total_count} задач",
        reply_markup=kb_builder.as_markup()
    )


@router.callback_query(F.data.startswith("tasks_page:"))
async def process_pagination(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    total_count = len(MOCK_TASKS)
    
    kb_builder = get_tasks_keyboard(page=page, total_tasks=api.get_tasks())
    
    await callback.message.edit_text(
        text=f"Всего {total_count} задач.",
        reply_markup=kb_builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("task_click:"))
async def process_task_click(callback: CallbackQuery):
    task_id = callback.data.split(":")[1]
    await callback.answer(text=f"Это задача #{task_id}", show_alert=True)


@router.callback_query(F.data == "noop")
async def process_noop(callback: CallbackQuery):
    await callback.answer()

async def register(dp: Dispatcher):
    logger.info(f"Number of tasks per page is {TASKS_PER_PAGE}")
    dp.include_router(router)