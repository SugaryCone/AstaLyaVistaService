from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

async def command(message: Message) -> None:
    builder = InlineKeyboardBuilder()
    for index in range(10):
        builder.button(text=f"#{index} Task name sta…", callback_data=f"task#{index}")
    builder.adjust(1, 1)
    await message.answer("There are 10 tasks", reply_markup=builder.as_markup())

async def button_task(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    for index in range(10):
        builder.button(text=f"#{index} Hello world", callback_data=f"bullshit#{index}")
    builder.adjust(1, 1)
    task_number = callback.data.split("#")[1]
    await callback.message.edit_text(text=f"You pressed button #{task_number}. There are 10 more tasks", reply_markup=builder.as_markup())
    await callback.answer()