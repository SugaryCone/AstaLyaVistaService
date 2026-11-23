from dotenv import load_dotenv
from os import getenv
import sys

import asyncio
import handlers.tasks
from loguru import logger

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.utils.formatting import Bold, Italic, Text, Code, TextLink

load_dotenv()

async def cmd_start(message: Message) -> None:
    await message.answer("Список команд:\n"
                         "/tasks [поисковая_строка] — обзор всех задач\n"
                         "/task &lt;id&gt; — информация о задаче\n"
                         "/newtask — создание задачи\n"
                         "/deltask &lt;id&gt — удаление задачи")

async def main() -> None:
    proxy = getenv("CLIENT_BOT_PROXY")
    if proxy is not None:
        logger.info(f"Proxy is used: {proxy}")
    bot = Bot(
        token=getenv("CLIENT_BOT_TOKEN"),
        session=AiohttpSession(proxy=proxy),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.message.register(cmd_start, Command("start"))
    await handlers.tasks.register(dp)
    logger.info("Polling started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logger.configure(handlers=[
        {"sink": sys.stderr, "format": "{level:8s} | {message}", "level": "INFO"}
    ])
    asyncio.run(main())