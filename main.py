import asyncio
import os
import re
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

TOKEN = os.environ.get("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

class CalcState(StatesGroup):
    waiting_for_margin_data = State()
    waiting_for_target_price_data = State()

def get_main_keyboard():
    kb = [
        [types.KeyboardButton(text="📊 Рассчитать маржу")],
        [types.KeyboardButton(text="🎯 Подобрать идеальную цену")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_cancel_keyboard():
    kb = [[types.KeyboardButton(text="❌ Отмена")]]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def parse_numbers(text: str):
    clean_text = text.replace('%', '').replace(',', '.')
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", clean_text)
    return [float(n) for n in numbers]

# --- Старт и Отмена ---
@dp.message(CommandStart())
@dp.message(F.text == "❌ Отмена")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        f"Я бот **«Маржа Ozon»**.\n"
        f"Выбери нужный режим в меню ниже 👇",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

# --- Режим 1: Расчёт маржи ---
@dp.message(F.text == "📊 Рассчитать маржу")
async def start_calc_margin(message: types.Message, state: FSMContext):
    await state.set_state(CalcState.waiting_for_margin_data)
    await message.answer(
        "📊 **Введите 6 значений через пробел:**\n\n"
        "1. Цена продажи (₽)\n"
        "2. Себестоимость (₽)\n"
        "3. Комиссия Ozon (%)\n"
        "4. Логистика (₽)\n"
        "5. Эквайринг (%)\n"
        "6. Налог (%)\n\n"
        "💡 **Пример:**\n"
        "`1500 500 15 150 1.5 6`",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(CalcState.waiting_for_margin_data)
async def process_margin_calc(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) < 6:
        await message.answer(
            "⚠️ **Нужно ввести 6 чисел через пробел!**\n\n"
            "Пример: `1500 500 15 150 1.5 6`", 
            parse_mode="Markdown"
        )
        return

    price, cost, comm_pct, deliv, acq_pct, tax_pct = parts[:6]

    ozon_comm = price * (comm_pct / 100)
    acquiring = price * (acq_pct / 100)
    tax = price * (tax_pct / 100)
    
    total_costs = cost + ozon_comm + deliv + acquiring + tax
    net_profit = price - total_costs
    margin = (net_profit / price) * 100 if price else 0
    roi = (net_profit / cost) * 100 if cost else 0

    text = (
        f"📊 **Результаты расчета:**\n\n"
        f"💵 Цена продажи: **{price:.2f} ₽**\n"
        f"📦 Закупка: **{cost:.2f} ₽**\n\n"
        f"💸 **Расходы:**\n"
        f"• Комиссия Ozon ({comm_pct}%): **{ozon_comm:.2f} ₽**\n"
        f"• Логистика: **{deliv:.2f} ₽**\n"
        f"• Эквайринг ({acq_pct}%): **{acquiring:.2f} ₽**\n"
        f"• Налог ({tax_pct}%): **{tax:.2f} ₽**\n"
        f"-------------------------------\n"
        f"💰 **Чистая прибыль:** **{net_profit:.2f} ₽**\n"
        f"📈 **Маржинальность:** **{margin:.2f}%**\n"
        f"🚀 **ROI:** **{roi:.2f}%**"
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    await state.clear()

# --- Режим 2: Подбор цены ---
@dp.message(F.text == "🎯 Подобрать идеальную цену")
async def start_calc_price(message: types.Message, state: FSMContext):
    await state.set_state(CalcState.waiting_for_target_price_data)
    await message.answer(
        "🎯 **Введите 6 значений через пробел:**\n\n"
        "1. Желаемая чистая прибыль (₽)\n"
        "2. Себестоимость (₽)\n"
        "3. Комиссия Ozon (%)\n"
        "4. Логистика (₽)\n"
        "5. Эквайринг (%)\n"
        "6. Налог (%)\n\n"
        "💡 **Пример:**\n"
        "`300 500 15 150 1.5 6`",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(CalcState.waiting_for_target_price_data)
async def process_target_price(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) < 6:
        await message.answer(
            "⚠️ **Нужно ввести 6 чисел через пробел!**\n\n"
            "Пример: `300 500 15 150 1.5 6`", 
            parse_mode="Markdown"
        )
        return

    target_profit, cost, comm_pct, deliv, acq_pct, tax_pct = parts[:6]

    pct_sum = (comm_pct + acq_pct + tax_pct) / 100
    if pct_sum >= 1:
        await message.answer("⚠️ Сумма комиссий и налогов не может быть 100% или больше!")
        return

    needed_price = (target_profit + cost + deliv) / (1 - pct_sum)

    await message.answer(
        f"🎯 **Рекомендуемая цена:** **{needed_price:.2f} ₽**\n\n"
        f"При такой цене вы заработаете **{target_profit:.2f} ₽** чистой прибыли.",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    await state.clear()

# --- Ловец всех остальных текстовых сообщений (чтобы бот НЕ молчал) ---
@dp.message()
async def fallback_handler(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    # Если пользователь просто отправил 6 чисел вне режима, сработает расчёт маржи
    if len(parts) >= 6:
        await process_margin_calc(message, state)
    else:
        await message.answer(
            "🤖 Я не понял команду.\n\n"
            "Пожалуйста, выберите режим в меню ниже или нажмите `/start`",
            reply_markup=get_main_keyboard()
        )

# --- Веб-сервер для Render ---
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
