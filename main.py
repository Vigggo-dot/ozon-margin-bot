import asyncio
import os
import re
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
    waiting_for_niche_data = State()

# --- Главное меню (Клавиатура под полем ввода) ---
def get_main_keyboard():
    kb = [
        [types.KeyboardButton(text="📊 Рассчитать маржу"), types.KeyboardButton(text="🎯 Подобрать цену")],
        [types.KeyboardButton(text="📈 Анализ ниши / Порог входа")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- Inline-кнопки под ответами ---
def get_action_inline_kb():
    kb = [
        [
            types.InlineKeyboardButton(text="🧮 Рассчитать маржу", callback_data="act_margin"),
            types.InlineKeyboardButton(text="🎯 Подобрать цену", callback_data="act_price")
        ],
        [
            types.InlineKeyboardButton(text="📈 Оценить нишу", callback_data="act_niche")
        ]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

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
        f"Привет, **{message.from_user.first_name}**! 👋\n\n"
        f"🚀 Я твой аналитический ассистент по маркетплейсу **Ozon**.\n\n"
        f"Чем займемся сегодня?\n"
        f"• Посчитаем чистую прибыль и ROI\n"
        f"• Подберем идеальную цену продажи\n"
        f"• Оценим потенциал и риски ниши\n\n"
        f"Выбери нужный режим ниже 👇",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

# --- Режим 1: Расчёт маржи ---
@dp.message(F.text == "📊 Рассчитать маржу")
@dp.callback_query(F.data == "act_margin")
async def start_calc_margin(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.waiting_for_margin_data)
    text = (
        "📊 **Расчет чистой прибыли и маржи**\n\n"
        "Отправьте **6 чисел через пробел**:\n"
        "1️⃣ Цена продажи (₽)\n"
        "2️⃣ Себестоимость / закупка (₽)\n"
        "3️⃣ Комиссия Ozon (%)\n"
        "4️⃣ Логистика (₽)\n"
        "5️⃣ Эквайринг (%)\n"
        "6️⃣ Налог (%)\n\n"
        "💡 **Пример ввода:**\n`1500 500 15 150 1.5 6`"
    )
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(text, reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(text, reply_markup=get_cancel_keyboard(), parse_mode="Markdown")

@dp.message(CalcState.waiting_for_margin_data)
async def process_margin_calc(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) < 6:
        await message.answer("⚠️ **Нужно ввести 6 чисел через пробел!**\nПример: `1500 500 15 150 1.5 6`", parse_mode="Markdown")
        return

    price, cost, comm_pct, deliv, acq_pct, tax_pct = parts[:6]

    ozon_comm = price * (comm_pct / 100)
    acquiring = price * (acq_pct / 100)
    tax = price * (tax_pct / 100)
    
    total_costs = cost + ozon_comm + deliv + acquiring + tax
    net_profit = price - total_costs
    margin = (net_profit / price) * 100 if price else 0
    roi = (net_profit / cost) * 100 if cost else 0

    if margin < 12 or net_profit < 100:
        verdict = "⚠️ **Опасно!** Очень узкая маржа. Любая акция или рекламные расходы уведут вас в минус."
    elif margin >= 25 and roi >= 60:
        verdict = "🔥 **Пушка!** Высокая маржинальность. Товар отлично подходит для масштабирования."
    else:
        verdict = "👍 **Адекватно.** Нормальная рабочая экономика. Главное — держать под контролем ДРР (рекламу)."

    text = (
        f"📊 **ФИНАНСОВЫЙ РАСКЛАД**\n"
        f"───────────────────\n"
        f"💵 Цена продажи: **{price:.2f} ₽**\n"
        f"📦 Закупка: **{cost:.2f} ₽**\n\n"
        f"💸 **Структура расходов:**\n"
        f"• Комиссия Ozon ({comm_pct}%): **{ozon_comm:.2f} ₽**\n"
        f"• Логистика: **{deliv:.2f} ₽**\n"
        f"• Эквайринг ({acq_pct}%): **{acquiring:.2f} ₽**\n"
        f"• Налог ({tax_pct}%): **{tax:.2f} ₽**\n"
        f"───────────────────\n"
        f"💰 **Чистая прибыль:** **{net_profit:.2f} ₽**\n"
        f"📈 **Маржинальность:** **{margin:.2f}%**\n"
        f"🚀 **ROI (окупаемость):** **{roi:.2f}%**\n\n"
        f"{verdict}"
    )
    await message.answer(text, reply_markup=get_action_inline_kb(), parse_mode="Markdown")
    await state.clear()

# --- Режим 2: Подбор цены ---
@dp.message(F.text == "🎯 Подобрать цену")
@dp.callback_query(F.data == "act_price")
async def start_calc_price(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.waiting_for_target_price_data)
    text = (
        "🎯 **Подбор идеальной цены продажи**\n\n"
        "Отправьте **6 чисел через пробел**:\n"
        "1️⃣ Желаемая чистая прибыль (₽)\n"
        "2️⃣ Себестоимость / закупка (₽)\n"
        "3️⃣ Комиссия Ozon (%)\n"
        "4️⃣ Логистика (₽)\n"
        "5️⃣ Эквайринг (%)\n"
        "6️⃣ Налог (%)\n\n"
        "💡 **Пример ввода:**\n`300 500 15 150 1.5 6`"
    )
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(text, reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(text, reply_markup=get_cancel_keyboard(), parse_mode="Markdown")

@dp.message(CalcState.waiting_for_target_price_data)
async def process_target_price(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) < 6:
        await message.answer("⚠️ **Нужно ввести 6 чисел через пробел!**\nПример: `300 500 15 150 1.5 6`", parse_mode="Markdown")
        return

    target_profit, cost, comm_pct, deliv, acq_pct, tax_pct = parts[:6]

    pct_sum = (comm_pct + acq_pct + tax_pct) / 100
    if pct_sum >= 1:
        await message.answer("⚠️ Сумма комиссий и налогов не может быть 100% или больше!")
        return

    needed_price = (target_profit + cost + deliv) / (1 - pct_sum)

    text = (
        f"🎯 **РЕКОМЕНДУЕМАЯ ЦЕНА**\n"
        f"───────────────────\n"
        f"Чтобы забирать чистыми **{target_profit:.2f} ₽** с каждой продажи:\n\n"
        f"🏷️ Выставляйте цену: **{needed_price:.2f} ₽**\n\n"
        f"💡 *Совет:* Сравните эту цену с ТОП-10 карточками на Ozon. Если ваша цена ниже конкурентов — вы в идеальной позиции!"
    )
    await message.answer(text, reply_markup=get_action_inline_kb(), parse_mode="Markdown")
    await state.clear()

# --- Режим 3: Экспресс-анализ ниши ---
@dp.message(F.text == "📈 Анализ ниши / Порог входа")
@dp.callback_query(F.data == "act_niche")
async def start_niche_analysis(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.waiting_for_niche_data)
    text = (
        "📈 **Экспресс-оценка ниши и порога входа**\n\n"
        "Отправьте **4 значения через пробел**:\n"
        "1️⃣ Средняя цена товара в нише (₽)\n"
        "2️⃣ Закупка товара (₽)\n"
        "3️⃣ Ожидаемый ДРР / Реклама (%)\n"
        "4️⃣ Планируемый объем продаж (шт/мес)\n\n"
        "💡 **Пример ввода:**\n`1200 400 15 200`\n"
        "*(Цена 1200₽, закупка 400₽, реклама 15%, продаем 200 шт в месяц)*"
    )
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(text, reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(text, reply_markup=get_cancel_keyboard(), parse_mode="Markdown")

@dp.message(CalcState.waiting_for_niche_data)
async def process_niche_analysis(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) < 4:
        await message.answer("⚠️ **Нужно ввести 4 числа через пробел!**\nПример: `1200 400 15 200`", parse_mode="Markdown")
        return

    avg_price, cost, drr_pct, monthly_sales = parts[:4]

    # Усреднённые комиссии Ozon (~20% комиссия + логистика ~150р + 2% эквайринг + 6% налог)
    est_ozon_fees = avg_price * 0.22 + 150 + (avg_price * 0.06)
    est_ad_costs = avg_price * (drr_pct / 100)
    
    unit_profit = avg_price - cost - est_ozon_fees - est_ad_costs
    total_revenue = avg_price * monthly_sales
    total_net_profit = unit_profit * monthly_sales
    required_capital = (cost * monthly_sales) + (monthly_sales * 100) # закупка + резерв на логистику/упаковку

    if unit_profit <= 0:
        niche_verdict = "⛔ **Ниша перегрета!** При таком ДРР и закупке вы будете работать в убыток."
    elif unit_profit < 150:
        niche_verdict = "⚡ **Высокий риск.** Низкая прибыль с единицы. Требуется объём или более дешевая закупка."
    else:
        niche_verdict = "🟢 **Перспективная ниша!** Запас прочности позволяет конкурировать и закладывать бюджет на продвижение."

    text = (
        f"📈 **АНАЛИЗ ПОТЕНЦИАЛА НИШИ**\n"
        f"───────────────────\n"
        f"💵 Средний чек: **{avg_price:.2f} ₽**\n"
        f"📊 Оборот при {int(monthly_sales)} шт/мес: **{total_revenue:,.2f} ₽**\n\n"
        f"💰 **Чистый заработок с 1 шт:** **{unit_profit:.2f} ₽**\n"
        f"🏆 **Чистая прибыль в месяц:** **{total_net_profit:,.2f} ₽**\n"
        f"💼 **Мин. капитал на закупку:** **{required_capital:,.2f} ₽**\n"
        f"───────────────────\n"
        f"{niche_verdict}"
    )
    await message.answer(text, reply_markup=get_action_inline_kb(), parse_mode="Markdown")
    await state.clear()

# --- Ловец всего остального ---
@dp.message()
async def fallback_handler(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) >= 6:
        await process_margin_calc(message, state)
    else:
        await message.answer(
            "🤖 Выбери команду в меню или нажми `/start`",
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
