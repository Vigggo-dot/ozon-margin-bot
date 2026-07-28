import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = "8592208675:AAFJbR8c1kC0TzuhJjf-Gke21TREre5R0CA"

bot = Bot(token=TOKEN)
dp = Dispatcher()

class CalcState(StatesGroup):
    waiting_for_data = State()

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    kb = [
        [types.KeyboardButton(text="📊 Рассчитать маржу")],
        [types.KeyboardButton(text="🎯 Подобрать идеальную цену")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        f"Я бот **«Маржа Ozon»**.\n"
        f"Помогу рассчитать реальную чистую прибыль с учетом всех комиссий Ozon или подберу цену под нужный заработок.\n\n"
        f"Выбери режим ниже 👇",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# Фейковый сервер для Render, чтобы сервис не выключался
async def handle(request):
    return web.Response(text="Bot is running!")

async def main():
    # Запускаем фоновый веб-сервер на порту, который просит Render
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    asyncio.create_task(site.start())

    # Запускаем поллинг бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
