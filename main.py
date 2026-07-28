import asyncio
import os
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

@dp.message(F.text == "📊 Рассчитать маржу")
async def calc_mode(message: types.Message, state: FSMContext):
    await message.answer(
        "Введите данные через пробел:\n"
        "`[Закупка] [Цена на Ozon] [Комиссия %] [Логистика ₽]`\n\n"
        "Пример: `500 1500 15 120`",
        parse_mode="Markdown"
    )
    await state.set_state(CalcState.waiting_for_data)

@dp.message(CalcState.waiting_for_data)
async def process_calc(message: types.Message, state: FSMContext):
    try:
        data = message.text.split()
        buy = float(data[0])
        sell = float(data[1])
        comm_pct = float(data[2])
        logistics = float(data[3])
        
        comm_rub = sell * (comm_pct / 100)
        acquiring = sell * 0.015
        tax = sell * 0.06
        
        profit = sell - buy - comm_rub - logistics - acquiring - tax
        margin = (profit / sell) * 100 if sell > 0 else 0
        roi = (profit / buy) * 100 if buy > 0 else 0
        
        verdict = "🟢 Отличный маржинальный товар!" if margin >= 20 else "🟡 Высокие риски/мало прибыли!" if margin > 0 else "🔴 ТОВАР В УБЫТОК!"

        res = (
            f"📊 **Результат расчёта:**\n\n"
            f"💵 Цена продажи: {sell} ₽\n"
            f"📦 Закупка: {buy} ₽\n"
            f"🔻 Комиссия Ozon ({comm_pct}%): {comm_rub:.1f} ₽\n"
            f"🚚 Логистика: {logistics} ₽\n"
            f"💳 Эквайринг (1.5%): {acquiring:.1f} ₽\n"
            f"🏛 Налог (УСН 6%): {tax:.1f} ₽\n"
            f"───────────────────\n"
            f"💰 **Чистая прибыль: {profit:.1f} ₽**\n"
            f"📈 **Маржинальность: {margin:.1f}%**\n"
            f"🚀 **ROI: {roi:.1f}%**\n\n"
            f"{verdict}"
        )
        await message.answer(res, parse_mode="Markdown")
        await state.clear()
    except Exception:
        await message.answer("⚠️ Ошибка ввода! Введите 4 числа через пробел, например: `500 1500 15 120`", parse_mode="Markdown")

async def main():
    print("Бот запущен в облаке!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
