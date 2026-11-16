from os import getenv
from dotenv import load_dotenv
from dataclasses import dataclass

import asyncio
import handlers.tasks

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.client.session.aiohttp import AiohttpSession

load_dotenv()

@dataclass
class ClientSettings:
    bot_token: str
    http_proxy: str

def get_settings() -> ClientSettings:
    return ClientSettings(
        bot_token=getenv("CLIENT_BOT_TOKEN"),
        http_proxy=getenv("http_proxy"),
    )

async def cmd_start(message: Message) -> None:
    await message.answer("What can I do for you?")

async def main() -> None:
    settings = get_settings()
    if settings.http_proxy != None:
        print(f"Running with proxy: {settings.http_proxy}")
    bot = Bot(
        token=settings.bot_token,
        session=AiohttpSession(proxy=settings.http_proxy),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(handlers.tasks.command, Command("tasks"))
    dp.callback_query.register(handlers.tasks.button_task, F.data.startswith("task#"))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())