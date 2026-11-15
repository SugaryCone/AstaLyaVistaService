import os
from dotenv import load_dotenv
from dataclasses import dataclass

import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.client.session.aiohttp import AiohttpSession

load_dotenv()

@dataclass
class ClientSettings:
    bot_token: str
    http_proxy: str

def get_settings() -> ClientSettings:
    return ClientSettings(
        bot_token=os.environ["CLIENT_BOT_TOKEN"],
        http_proxy=os.environ.get("http_proxy"),
    )

aiogram_dispatcher = Dispatcher()

@aiogram_dispatcher.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Hello world!\n"
        "There is no spoon."
    )

@aiogram_dispatcher.message(F.text)
async def echo(message: Message) -> None:
    await message.answer(f"(echo) {message.text}")

async def main() -> None:
    settings = get_settings()
    if settings.http_proxy != None:
        print(f"Running with proxy: {settings.http_proxy}")
    bot = Bot(
        token=settings.bot_token,
        session=AiohttpSession(proxy=settings.http_proxy),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await aiogram_dispatcher.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())