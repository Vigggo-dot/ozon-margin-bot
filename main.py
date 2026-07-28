import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

TOKEN = os.environ.get("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

class CalcState(StatesGroup):
    waiting_for_margin_data = State()
    waiting_for_target_price_data = State()

@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    kb = [
        [types.KeyboardButton(text="📊 Рассчитать маржу")],
        [types.KeyboardButton(text="🎯 Подобрать идеальную цену")]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        f"Я бот **«Маржа Ozon»**.\n"
        f"Помогу рассчитать реальную чистую прибыль или подберу цену продажи.\n\n"
        f"Выбери режим ниже 👇",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# --- Режим 1: Расчёт маржи ---
@dp.message(F.text == "📊 Рассчитать маржу")
async def start_calc_margin(message: types.Message, state: FSMContext):
    await state.set_state(CalcState.waiting_for_margin_data)
    await message.answer(
        "📥 **Введите данные через пробел:**\n\n"
        "`Цена_продажи Закупка Комиссия_% Логистика Эквайринг_% Налог_%`\n\n"
        "💡 **Пример:**\n"
        "`1500 500 15 150 1.5 6`\n\n"
        "*(где 1500 — цена, 500 — себестоимость, 15% — комиссия Ozon, 150₽ — логистика, 1.5% — эквайринг, 6% — налог)*",
        parse_mode="Markdown"
    )

@dp.message(CalcState.waiting_for_margin_data)
async def process_margin_calc(message: types.Message, state: FSMContext):
    try:
        parts = list(map(float, message.text.replace(',', '.').split()))
        if len(parts) < 6:
            raise ValueError

        price, cost, comm_pct, deliv, acq_pct, tax_pct = parts[:6]

        ozon_comm = price * (comm_pct / 100)
        acquiring = price * (acq_pct / 100)
        tax = price * (tax_pct / 100)
        
        total_costs = cost + ozon_comm + deliv + acquiring + tax
        net_profit = price - total_costs
        margin = (net_profit / price) * 100
        roi = (net_profit / cost) * 100

        text = (
            f"📊 **Результаты расчета:**\n\n"
            f"💵 Цена продажи: **{price:.2f} ₽**\n"
            f"📦 Закупка/Себестоимость: **{cost:.2f} ₽**\n\n"
            f"💸 **Расходы:**\n"
            f"• Комиссия Ozon ({comm_pct}%): **{ozon_comm:.2f} ₽**\n"
            f"• Логистика: **{deliv:.2f} ₽**\n"
            f"• Эквайринг ({acq_pct}%): **{acquiring:.2f} ₽**\n"
            f"• Налог ({tax_pct}%): **{tax:.2f} ₽**\n"
            f"-------------------------------\n"
            f"💰 **Чистая прибыль:** `{net_profit:.2f} ₽`\n"
            f"📈 **Маржинальность:** `{margin:.2f}%`\n"
            f"🚀 **ROI (окупаемость):** `{roi:.2f}%`"
        )
        await message.answer(text, parse_mode="Markdown")
        await state.clear()
    except Exception:
        await message.answer("⚠️ Ошибка ввода! Введите 6 чисел через пробел, как в примере.")

# --- Режим 2: Подбор цены ---
@dp.message(F.text == "🎯 Подобрать идеальную цену")
async def start_calc_price(message: types.Message, state: FSMContext):
    await state.set_state(CalcState.waiting_for_target_price_data)
    await message.answer(
        "🎯 **Введите данные для подбора цены через пробел:**\n\n"
        "`Желаемая_прибыль Закупка Комиссия_% Логистика Эквайринг_% Налог_%`\n\n"
        "💡 **Пример:**\n"
        "`300 500 15 150 1.5 6`\n\n"
        "*(300₽ — сколько хочешь чистыми с штуки)*",
        parse_mode="Markdown"
    )

@dp.message(CalcState.waiting_for_target_price_data)
async def process_target_price(message: types.Message, state: FSMContext):
    try:
        parts = list(map(float, message.text.replace(',', '.').split()))
        if len(parts) < 6:
            raise ValueError

        target_profit, cost, comm_pct, deliv, acq_pct, tax_pct = parts[:6]

        pct_sum = (comm_pct + acq_pct + tax_pct) / 100
        if pct_sum >= 1:
            await message.answer("⚠️ Сумма комиссий и налогов не может быть 100% или больше!")
            return

        needed_price = (target_profit + cost + deliv) / (1 - pct_sum)

        await message.answer(
            f"🎯 **Идеальная цена продажи:** `{needed_price:.2f} ₽`\n\n"
            f"Чтобы зарабатывать **{target_profit:.2f} ₽** чистыми с товара при закупке в {cost:.2f} ₽.",
            parse_mode="Markdown"
        )
        await state.clear()
    except Exception:
        await message.answer("⚠️ Ошибка ввода! Введите 6 чисел через пробел, как в примере.")

# --- Веб-сервер для поддержания Render ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def main():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    asyncio.create_task(site.start())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
