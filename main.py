import asyncio
import os
import re
import io
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import matplotlib
matplotlib.use('Agg')  # Фоновый режим для серверов без GUI
import matplotlib.pyplot as plt

TOKEN = os.environ.get("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

class CalcState(StatesGroup):
    waiting_for_margin_data = State()
    waiting_for_target_price_data = State()
    waiting_for_niche_data = State()

# --- Тексты и Уютный Стиль ---
START_TEXT = (
    "Приветствую! ✨\n\n"
    "Я твой уютный аналитический ассистент по Ozon. Моя задача — бережно просчитать "
    "юнит-экономику, подсказать безопасную цену и оценить риски входа в нишу.\n\n"
    "Выбери, с чего начнем:"
)

# --- Клавиатуры ---
def get_main_keyboard():
    kb = [
        [types.KeyboardButton(text="📊 Рассчитать маржу"), types.KeyboardButton(text="🎯 Подобрать цену")],
        [types.KeyboardButton(text="📈 Экспресс-анализ ниши")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_action_inline_kb():
    kb = [
        [
            types.InlineKeyboardButton(text="📊 Рассчитать маржу", callback_data="act_margin"),
            types.InlineKeyboardButton(text="🎯 Подобрать цену", callback_data="act_price")
        ],
        [
            types.InlineKeyboardButton(text="📈 Анализ ниши", callback_data="act_niche")
        ]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

def get_cancel_inline_kb():
    kb = [[types.InlineKeyboardButton(text="❌ Отменить ввод", callback_data="act_cancel")]]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

def parse_numbers(text: str):
    clean_text = text.replace('%', '').replace(',', '.')
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", clean_text)
    return [float(n) for n in numbers]

# --- Генератор Графиков ---
def generate_chart_png(labels, values, colors, title):
    fig, ax = plt.subplots(figsize=(6, 4), dpi=120)
    fig.patch.set_facecolor('#1E1E2E')  # Мягкий тёмный фон
    ax.set_facecolor('#1E1E2E')

    # Круговая диаграмма
    wedges, texts, autotexts = ax.pie(
        values, 
        labels=labels, 
        colors=colors, 
        autopct='%1.1f%%',
        startangle=140,
        textprops=dict(color="w", weight="bold"),
        pctdistance=0.75,
        wedgeprops=dict(width=0.4, edgecolor='#1E1E2E', linewidth=2) # Стильный Doughnut chart
    )

    for t in texts:
        t.set_color('#CDD6F4')
        t.set_fontsize(10)
    for at in autotexts:
        at.set_color('#11111B')
        at.set_fontsize(9)

    ax.set_title(title, color='#CDD6F4', fontsize=12, pad=15, weight="bold")
    
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), transparent=False)
    buf.seek(0)
    plt.close(fig)
    return buf

# --- Старт и Отмена ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(START_TEXT, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "act_cancel")
async def cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Ввод отменен", show_alert=False)
    await callback.message.edit_text("💡 Ввод отменен. Выберите нужное действие из меню ниже:")

# --- Режим 1: Расчёт маржи ---
@dp.message(F.text == "📊 Рассчитать маржу")
@dp.callback_query(F.data == "act_margin")
async def start_calc_margin(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.waiting_for_margin_data)
    prompt = (
        "☕ **Расчёт юнит-экономики**\n\n"
        "Отправьте **6 чисел через пробел**:\n"
        "1. Цена продажи (₽)\n"
        "2. Себестоимость закупки (₽)\n"
        "3. Комиссия Ozon (%)\n"
        "4. Логистика (₽)\n"
        "5. Эквайринг (%)\n"
        "6. Налог (%)\n\n"
        "📋 _Пример:_ `1500 500 15 150 1.5 6`"
    )
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(prompt, reply_markup=get_cancel_inline_kb(), parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(prompt, reply_markup=get_cancel_inline_kb(), parse_mode="Markdown")

@dp.message(CalcState.waiting_for_margin_data)
async def process_margin_calc(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) < 6:
        await message.answer("⚠️ Пожалуйста, введите **6 чисел** через пробел.\nПример: `1500 500 15 150 1.5 6`", parse_mode="Markdown")
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
        verdict = "⚠️ **Внимание:** Маржа довольно узкая. Любые скидки или акции могут увести продажи в минус."
    elif margin >= 25 and roi >= 60:
        verdict = "✨ **Отличный вариант!** Высокая маржинальность позволяет активно инвестировать в рекламу."
    else:
        verdict = "🌱 **Рабочая модель.** Нормальные показатели для спокойных продаж."

    text = (
        f"📊 **Анализ юнит-экономики**\n"
        f"═══════════════════\n"
        f"🏷️ Цена: **{price:.2f} ₽**  |  📦 Закупка: **{cost:.2f} ₽**\n\n"
        f"💸 **Расходы с продажи:**\n"
        f"• Комиссия Ozon ({comm_pct}%): **{ozon_comm:.2f} ₽**\n"
        f"• Логистика: **{deliv:.2f} ₽**\n"
        f"• Эквайринг ({acq_pct}%): **{acquiring:.2f} ₽**\n"
        f"• Налог ({tax_pct}%): **{tax:.2f} ₽**\n"
        f"═══════════════════\n"
        f"💰 **Чистая прибыль:** **{net_profit:.2f} ₽**\n"
        f"📈 **Маржинальность:** **{margin:.2f}%**\n"
        f"🚀 **ROI:** **{roi:.2f}%**\n\n"
        f"{verdict}"
    )

    # Генерация графика
    if net_profit > 0:
        labels = ['Закупка', 'Комиссия', 'Логистика', 'Эквайринг/Налог', 'Прибыль']
        values = [cost, ozon_comm, deliv, acquiring + tax, net_profit]
        colors = ['#F38BA8', '#FAB387', '#F9E2AF', '#A6E3A1', '#89B4FA']
        
        chart_buf = generate_chart_png(labels, values, colors, "Структура цены товара")
        photo = types.BufferedInputFile(chart_buf.read(), filename="chart.png")
        await message.answer_photo(photo, caption=text, reply_markup=get_action_inline_kb(), parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=get_action_inline_kb(), parse_mode="Markdown")

    await state.clear()

# --- Режим 2: Подбор цены ---
@dp.message(F.text == "🎯 Подобрать цену")
@dp.callback_query(F.data == "act_price")
async def start_calc_price(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.waiting_for_target_price_data)
    prompt = (
        "🎯 **Подбор оптимальной цены**\n\n"
        "Отправьте **6 чисел через пробел**:\n"
        "1. Желаемая прибыль с штуки (₽)\n"
        "2. Себестоимость закупки (₽)\n"
        "3. Комиссия Ozon (%)\n"
        "4. Логистика (₽)\n"
        "5. Эквайринг (%)\n"
        "6. Налог (%)\n\n"
        "📋 _Пример:_ `300 500 15 150 1.5 6`"
    )
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(prompt, reply_markup=get_cancel_inline_kb(), parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(prompt, reply_markup=get_cancel_inline_kb(), parse_mode="Markdown")

@dp.message(CalcState.waiting_for_target_price_data)
async def process_target_price(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) < 6:
        await message.answer("⚠️ Пожалуйста, введите **6 чисел** через пробел.\nПример: `300 500 15 150 1.5 6`", parse_mode="Markdown")
        return

    target_profit, cost, comm_pct, deliv, acq_pct, tax_pct = parts[:6]

    pct_sum = (comm_pct + acq_pct + tax_pct) / 100
    if pct_sum >= 1:
        await message.answer("⚠️ Сумма комиссий и налогов не может превышать 100%.")
        return

    needed_price = (target_profit + cost + deliv) / (1 - pct_sum)

    text = (
        f"🎯 **Рекомендуемая розничная цена**\n"
        f"═══════════════════\n"
        f"Чтобы забирать чистыми **{target_profit:.2f} ₽** с каждой продажи:\n\n"
        f"🏷️ Минимальная цена: **{needed_price:.2f} ₽**\n\n"
        f"💡 _Совет:_ Сверьте эту цену с топовыми продавцами в категории."
    )
    await message.answer(text, reply_markup=get_action_inline_kb(), parse_mode="Markdown")
    await state.clear()

# --- Режим 3: Экспресс-анализ ниши ---
@dp.message(F.text == "📈 Экспресс-анализ ниши")
@dp.callback_query(F.data == "act_niche")
async def start_niche_analysis(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.waiting_for_niche_data)
    prompt = (
        "📈 **Экспресс-оценка ниши**\n\n"
        "Отправьте **4 значения через пробел**:\n"
        "1. Средняя цена в нише (₽)\n"
        "2. Себестоимость закупки (₽)\n"
        "3. Ожидаемый ДРР / Реклама (%)\n"
        "4. Планируемый объем (шт/мес)\n\n"
        "📋 _Пример:_ `1200 400 15 200`"
    )
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(prompt, reply_markup=get_cancel_inline_kb(), parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(prompt, reply_markup=get_cancel_inline_kb(), parse_mode="Markdown")

@dp.message(CalcState.waiting_for_niche_data)
async def process_niche_analysis(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) < 4:
        await message.answer("⚠️ Введите **4 числа** через пробел.\nПример: `1200 400 15 200`", parse_mode="Markdown")
        return

    avg_price, cost, drr_pct, monthly_sales = parts[:4]

    est_ozon_fees = avg_price * 0.22 + 150 + (avg_price * 0.06)
    est_ad_costs = avg_price * (drr_pct / 100)
    
    unit_profit = avg_price - cost - est_ozon_fees - est_ad_costs
    total_revenue = avg_price * monthly_sales
    total_net_profit = unit_profit * monthly_sales
    required_capital = (cost * monthly_sales) + (monthly_sales * 100)

    if unit_profit <= 0:
        niche_verdict = "⛔ **Высокий риск:** Высокая вероятность уйти в минус при текущих расходах на рекламу."
    elif unit_profit < 150:
        niche_verdict = "⚡ **Узкая маржа:** Потребуется большой оборот или снижение себестоимости закупки."
    else:
        niche_verdict = "🟢 **Перспективно:** Хороший запас прочности для развития товара."

    text = (
        f"📈 **Потенциал ниши**\n"
        f"═══════════════════\n"
        f"💵 Средний чек: **{avg_price:.2f} ₽**\n"
        f"📊 Оборот ({int(monthly_sales)} шт/мес): **{total_revenue:,.2f} ₽**\n\n"
        f"💰 Прибыль с 1 шт: **{unit_profit:.2f} ₽**\n"
        f"🏆 Чистая прибыль в месяц: **{total_net_profit:,.2f} ₽**\n"
        f"💼 Старт. капитал на партию: **{required_capital:,.2f} ₽**\n"
        f"═══════════════════\n"
        f"{niche_verdict}"
    )
    await message.answer(text, reply_markup=get_action_inline_kb(), parse_mode="Markdown")
    await state.clear()

# --- Fallback ---
@dp.message()
async def fallback_handler(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) >= 6:
        await process_margin_calc(message, state)
    else:
        await message.answer("🤖 Воспользуйтесь меню ниже или нажмите `/start`", reply_markup=get_main_keyboard())

# --- Server ---
async def handle(request):
    return web.Response(text="Bot running smoothly!")

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
