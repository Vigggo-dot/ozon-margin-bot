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
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- НАСТРОЙКА АДМИНА И УЧЕТА ПОЛЬЗОВАТЕЛЕЙ ---
ADMIN_ID = 1061768872  # Ваш ID уже подставлен!

def log_user(user_id: int):
    """Сохраняет ID пользователя в файл users.txt, если его там нет"""
    try:
        if not os.path.exists("users.txt"):
            with open("users.txt", "w") as f:
                pass

        with open("users.txt", "r+") as f:
            users = f.read().splitlines()
            if str(user_id) not in users:
                f.seek(0, 2)
                f.write(f"{user_id}\n")
    except Exception as e:
        print(f"Ошибка логирования пользователя: {e}")

# --- НАСТРОЙКА ШРИФТА (КИРИЛЛИЦА) ---
FONT_NAME = 'Helvetica'
FONT_PATH = 'DejaVuSans.ttf'

def init_embedded_font():
    global FONT_NAME
    try:
        if not os.path.exists(FONT_PATH) or os.path.getsize(FONT_PATH) < 10000:
            system_fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
            ]
            found = False
            for sf in system_fonts:
                if os.path.exists(sf):
                    import shutil
                    shutil.copy(sf, FONT_PATH)
                    found = True
                    break
            
            if not found:
                import matplotlib.font_manager as fm
                for fpath in fm.findSystemFonts(fontpaths=None, fontext='ttf'):
                    if 'DejaVuSans' in fpath or 'dejavu' in fpath.lower() or 'liberation' in fpath.lower():
                        import shutil
                        shutil.copy(fpath, FONT_PATH)
                        break

        if os.path.exists(FONT_PATH) and os.path.getsize(FONT_PATH) > 10000:
            pdfmetrics.registerFont(TTFont('CyrillicFont', FONT_PATH))
            FONT_NAME = 'CyrillicFont'
            print("Шрифт успешно зарегистрирован в ReportLab!")
    except Exception as e:
        print(f"Ошибка инициализации шрифта: {e}")

init_embedded_font()

TOKEN = os.environ.get("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

user_last_calc = {}

class CalcState(StatesGroup):
    waiting_for_margin_data = State()
    waiting_for_target_price_data = State()
    waiting_for_niche_data = State()

# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    kb = [
        [types.KeyboardButton(text="📊 Рассчитать маржу"), types.KeyboardButton(text="🎯 Подобрать цену")],
        [types.KeyboardButton(text="📈 Экспресс-анализ ниши"), types.KeyboardButton(text="🦝 О боте и фишках")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_platform_inline_kb(action_prefix):
    kb = [
        [
            types.InlineKeyboardButton(text="📦 Ozon", callback_data=f"{action_prefix}_ozon"),
            types.InlineKeyboardButton(text="🟣 Wildberries", callback_data=f"{action_prefix}_wb"),
            types.InlineKeyboardButton(text="🟡 Яндекс Маркет", callback_data=f"{action_prefix}_ym")
        ],
        [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="act_menu")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

def get_action_inline_kb(calc_id=None):
    buttons = [
        [
            types.InlineKeyboardButton(text="📊 Рассчитать маржу", callback_data="act_margin"),
            types.InlineKeyboardButton(text="🎯 Подобрать цену", callback_data="act_price")
        ],
        [
            types.InlineKeyboardButton(text="📈 Анализ ниши", callback_data="act_niche"),
            types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="act_menu")
        ]
    ]
    if calc_id:
        buttons.insert(0, [types.InlineKeyboardButton(text="📄 Скачать брендированный PDF-отчёт", callback_data=f"pdf_{calc_id}")])
        
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_inline_kb():
    kb = [
        [types.InlineKeyboardButton(text="❌ Отменить ввод", callback_data="act_cancel")],
        [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="act_menu")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)

def parse_numbers(text: str):
    clean_text = text.replace('%', '').replace(',', '.')
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", clean_text)
    return [float(n) for n in numbers]

# --- ГРАФИКИ ---
def generate_doughnut_chart(labels, values, chart_colors, title):
    fig, ax = plt.subplots(figsize=(6, 4), dpi=120)
    fig.patch.set_facecolor('#1E1E2E')
    ax.set_facecolor('#1E1E2E')

    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=chart_colors, autopct='%1.1f%%',
        startangle=140, textprops=dict(color="w", weight="bold"),
        pctdistance=0.75, wedgeprops=dict(width=0.4, edgecolor='#1E1E2E', linewidth=2)
    )
    for t in texts:
        t.set_color('#CDD6F4')
        t.set_fontsize(9)
    for at in autotexts:
        at.set_color('#11111B')
        at.set_fontsize(8)

    ax.set_title(title, color='#CDD6F4', fontsize=11, pad=15, weight="bold")
    
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), transparent=False)
    buf.seek(0)
    plt.close(fig)
    return buf

def generate_bar_chart(categories, values, title):
    fig, ax = plt.subplots(figsize=(6, 3.8), dpi=120)
    fig.patch.set_facecolor('#1E1E2E')
    ax.set_facecolor('#1E1E2E')

    bar_colors = ['#FAB387', '#89B4FA', '#A6E3A1']
    bars = ax.bar(categories, values, color=bar_colors, width=0.5)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#CDD6F4')
    ax.spines['bottom'].set_color('#CDD6F4')
    ax.tick_params(colors='#CDD6F4', labelsize=9)

    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + (max(values)*0.02), f"{yval:,.0f} ₽", 
                ha='center', va='bottom', color='#CDD6F4', fontweight='bold', fontsize=8)

    ax.set_title(title, color='#CDD6F4', fontsize=11, pad=15, weight="bold")
    
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), transparent=False)
    buf.seek(0)
    plt.close(fig)
    return buf

# --- ГЕНЕРАЦИЯ БРЕНДИРОВАННОГО PDF ---
def create_pdf_report(calc_data, chart_buf):
    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('PdfTitle', parent=styles['Heading1'], fontName=FONT_NAME, fontSize=15, textColor=colors.HexColor('#1E1E2E'), spaceAfter=4)
    subtitle_style = ParagraphStyle('PdfSubTitle', parent=styles['Normal'], fontName=FONT_NAME, fontSize=9, textColor=colors.HexColor('#666666'), spaceAfter=10)
    cell_style = ParagraphStyle('PdfCell', parent=styles['Normal'], fontName=FONT_NAME, fontSize=9, textColor=colors.HexColor('#333333'))
    header_style = ParagraphStyle('PdfHeader', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10, textColor=colors.whitesmoke)
    footer_style = ParagraphStyle('PdfFooter', parent=styles['Normal'], fontName=FONT_NAME, fontSize=8, textColor=colors.HexColor('#888888'), alignment=1)

    platform_name = calc_data.get('platform', 'Ozon')
    
    story.append(Paragraph(f"Финансовый отчёт Unit-Economics ({platform_name})", title_style))
    story.append(Paragraph("Сгенерировано умным ботом-аналитиком селлеров", subtitle_style))
    story.append(Spacer(1, 5))

    table_data = [[
        Paragraph("<b>Параметр</b>", header_style), 
        Paragraph("<b>Значение</b>", header_style)
    ]]
    
    for k, v in calc_data['table'].items():
        table_data.append([
            Paragraph(str(k), cell_style), 
            Paragraph(str(v), cell_style)
        ])

    t = Table(table_data, colWidths=[230, 220])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E1E2E')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F9F9F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#DDDDDD')),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    badge_text = calc_data.get('badge', 'Анализ рынка')
    verdict_text = calc_data.get('verdict', '')

    story.append(Paragraph(f"<b>Статус / Титул:</b> {badge_text}", cell_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Вердикт аналитика:</b> {verdict_text}", cell_style))
    story.append(Spacer(1, 12))

    if chart_buf:
        chart_buf.seek(0)
        img = Image(chart_buf, width=380, height=240)
        story.append(img)
    
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CCCCCC'), spaceBefore=5, spaceAfter=8))
    story.append(Paragraph("Полезный инструмент для селлеров WB и Ozon | Сделано с заботой о бизнесе", footer_style))

    doc.build(story)
    pdf_buf.seek(0)
    return pdf_buf

# --- КОМАНДЫ И ОБРАБОТЧИКИ ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    log_user(message.from_user.id)  # Записываем пользователя в статистику
    await state.clear()
    await message.answer(
        "Приветствую! 🦝✨\n\n"
        "Я твой личный бизнес-ассистент по юнит-экономике для **Ozon**, **Wildberries** и **Яндекс Маркет**.\n\n"
        "Помогу быстро просчитать каждую позицию, уберечь от кассовых разрывов и найти идеальную цену.\n\n"
        "Выбери нужный режим в меню ниже 👇",
        reply_markup=get_main_keyboard(), parse_mode="Markdown"
    )

# --- КОМАНДА СТАТИСТИКИ ДЛЯ АДМИНА ---
@dp.message(F.text == "/stats")
async def show_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    count = 0
    if os.path.exists("users.txt"):
        with open("users.txt", "r") as f:
            count = len(f.read().splitlines())

    await message.answer(
        f"📊 **Статистика бота:**\n\n"
        f"👥 Уникальных пользователей: **{count}**",
        parse_mode="Markdown"
    )

@dp.message(F.text == "🦝 О боте и фишках")
async def about_bot(message: types.Message):
    text = (
        "🦝 **О вашем карманном аналитике**\n\n"
        "Привет! Я создан, чтобы избавить селлеров от рутинных таблиц и головной боли с комиссиями маркетплейсов.\n\n"
        "**Что я умею:**\n"
        "• Считать чистую маржу и ROI с учетом всех скрытых расходов (комиссии, логистика, налоги, эквайринг, ДРР).\n"
        "• Подбирать розничную цену под желаемую прибыль.\n"
        "• Оценивать потенциал новых ниш перед закупкой товара.\n"
        "• Давать классные PDF-отчёты с графиками, которыми удобно делиться в партнёрских чатах!\n\n"
        "Выбирай нужную кнопку в меню и давай посчитаем цифры! 🚀"
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "act_menu")
async def menu_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "💡 Главное меню.\nВыберите инструмент для работы:",
        reply_markup=get_action_inline_kb()
    )
    await callback.answer()

@dp.callback_query(F.data == "act_cancel")
async def cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Ввод отменен")
    await callback.message.edit_text("💡 Ввод отменен. Выберите действие:", reply_markup=get_action_inline_kb())

# --- РАССЧЕТ МАРЖИ ---
@dp.message(F.text == "📊 Рассчитать маржу")
@dp.callback_query(F.data == "act_margin")
async def choose_platform_margin(event: types.Message | types.CallbackQuery):
    text = "📦 Выберите маркетплейс для расчёта юнит-экономики:"
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=get_platform_inline_kb("margin"))
        await event.answer()
    else:
        await event.answer(text, reply_markup=get_platform_inline_kb("margin"))

@dp.callback_query(F.data.startswith("margin_"))
async def start_calc_margin(callback: types.CallbackQuery, state: FSMContext):
    platform = callback.data.split("_")[1].upper()
    if platform == "YM":
        platform = "Яндекс Маркет"
    await state.update_data(platform=platform)
    await state.set_state(CalcState.waiting_for_margin_data)
    
    prompt = (
        f"☕ **Расчёт юнит-экономики [{platform}]**\n\n"
        "Введите **6 или 7 чисел через пробел**:\n"
        "1. Цена продажи (₽)\n"
        "2. Себестоимость закупки (₽)\n"
        "3. Комиссия площадки (%)\n"
        "4. Логистика (₽)\n"
        "5. Эквайринг/Обработка (%)\n"
        "6. Налог (%)\n"
        "7. _(Опционально)_ Реклама/ДРР (%)\n\n"
        "📋 _Пример:_ `1500 500 15 150 1.5 6 10`"
    )
    await callback.message.edit_text(prompt, reply_markup=get_cancel_inline_kb(), parse_mode="Markdown")
    await callback.answer()

@dp.message(CalcState.waiting_for_margin_data)
async def process_margin_calc(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) < 6:
        await message.answer("⚠️ Введите минимум **6 чисел** через пробел.\nПример: `1500 500 15 150 1.5 6 10`", parse_mode="Markdown")
        return

    user_data = await state.get_data()
    platform = user_data.get('platform', 'OZON')

    price, cost, comm_pct, deliv, acq_pct, tax_pct = parts[:6]
    drr_pct = parts[6] if len(parts) >= 7 else 0.0

    comm_cost = price * (comm_pct / 100)
    acquiring = price * (acq_pct / 100)
    tax = price * (tax_pct / 100)
    ad_cost = price * (drr_pct / 100)
    
    total_costs = cost + comm_cost + deliv + acquiring + tax + ad_cost
    net_profit = price - total_costs
    margin = (net_profit / price) * 100 if price else 0
    roi = (net_profit / cost) * 100 if cost else 0

    if margin < 10 or net_profit < 100:
        badge = "Камикадзе с демпингом"
        verdict = "Маржа узкая. Риск уйти в минус при акциях или росте расходов."
    elif margin >= 25 and roi >= 60:
        badge = "Акула маркетплейсов"
        verdict = "Отличная экономика! Высокий запас прочности."
    else:
        badge = "Уверенный середнячок"
        verdict = "Нормальные рабочие показатели для старта."

    ad_str = f"\n• Реклама ДРР ({drr_pct}%): **{ad_cost:.2f} ₽**" if drr_pct > 0 else ""

    text = (
        f"📊 **Юнит-экономика [{platform}]**\n"
        f"═══════════════════\n"
        f"🏷️ Цена: **{price:.2f} ₽**  |  📦 Закупка: **{cost:.2f} ₽**\n\n"
        f"💸 **Расходы с продажи:**\n"
        f"• Комиссия ({comm_pct}%): **{comm_cost:.2f} ₽**\n"
        f"• Логистика: **{deliv:.2f} ₽**\n"
        f"• Эквайринг ({acq_pct}%): **{acquiring:.2f} ₽**\n"
        f"• Налог ({tax_pct}%): **{tax:.2f} ₽**"
        f"{ad_str}\n"
        f"═══════════════════\n"
        f"💰 **Чистая прибыль:** **{net_profit:.2f} ₽**\n"
        f"📈 **Маржинальность:** **{margin:.2f}%**\n"
        f"🚀 **ROI:** **{roi:.2f}%**\n\n"
        f"🏅 Статус: **{badge}**\n"
        f"💡 {verdict}"
    )

    calc_id = f"m_{message.from_user.id}"
    chart_buf = None
    if net_profit > 0:
        labels = ['Закупка', 'Комиссия', 'Логистика', 'Налоги/Экв.', 'Прибыль']
        values = [cost, comm_cost, deliv, acquiring + tax, net_profit]
        colors_list = ['#F38BA8', '#FAB387', '#F9E2AF', '#A6E3A1', '#89B4FA']
        
        if drr_pct > 0:
            labels.insert(4, 'Реклама')
            values.insert(4, ad_cost)
            colors_list.insert(4, '#CBA6F7')

        chart_buf = generate_doughnut_chart(labels, values, colors_list, f"Структура цены [{platform}]")

    user_last_calc[calc_id] = {
        'platform': platform,
        'table': {
            'Цена продажи': f"{price:.2f} руб",
            'Закупка': f"{cost:.2f} руб",
            'Комиссия': f"{comm_cost:.2f} руб ({comm_pct}%)",
            'Логистика': f"{deliv:.2f} руб",
            'Эквайринг + Налог': f"{acquiring + tax:.2f} руб",
            'Реклама (ДРР)': f"{ad_cost:.2f} руб ({drr_pct}%)",
            'Чистая прибыль': f"{net_profit:.2f} руб",
            'Маржинальность': f"{margin:.2f}%",
            'ROI': f"{roi:.2f}%"
        },
        'badge': badge,
        'verdict': verdict,
        'chart': chart_buf
    }

    if chart_buf:
        photo = types.BufferedInputFile(chart_buf.getvalue(), filename="chart.png")
        await message.answer_photo(photo, caption=text, reply_markup=get_action_inline_kb(calc_id), parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=get_action_inline_kb(calc_id), parse_mode="Markdown")

    await state.clear()

# --- ПОДОБРАТЬ ЦЕНУ ---
@dp.message(F.text == "🎯 Подобрать цену")
@dp.callback_query(F.data == "act_price")
async def start_calc_price(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.waiting_for_target_price_data)
    prompt = (
        "🎯 **Подбор оптимальной цены**\n\n"
        "Введите **6 чисел через пробел**:\n"
        "1. Желаемая прибыль (₽)\n"
        "2. Себестоимость закупки (₽)\n"
        "3. Комиссия площадки (%)\n"
        "4. Логистика (₽)\n"
        "5. Эквайринг (%)\n"
        "6. Налог (%)\n\n"
        "📋 _Пример:_ `300 500 15 150 1.5 6`"
    )
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(prompt, reply_markup=get_cancel_inline_kb(), parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(prompt, reply_markup=get_cancel_inline_kb(), parse_mode="Markdown")

@dp.message(CalcState.waiting_for_target_price_data)
async def process_target_price(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) < 6:
        await message.answer("⚠️ Введите **6 чисел** через пробел.\nПример: `300 500 15 150 1.5 6`", parse_mode="Markdown")
        return

    target_profit, cost, comm_pct, deliv, acq_pct, tax_pct = parts[:6]
    pct_sum = (comm_pct + acq_pct + tax_pct) / 100
    if pct_sum >= 1:
        await message.answer("⚠️ Сумма комиссий и налогов не может быть 100% и более.")
        return

    needed_price = (target_profit + cost + deliv) / (1 - pct_sum)

    text = (
        f"🎯 **Рекомендуемая розничная цена**\n"
        f"═══════════════════\n"
        f"Чтобы забирать чистыми **{target_profit:.2f} ₽** с единицы товара:\n\n"
        f"🏷️ Минимальная цена продажи: **{needed_price:.2f} ₽**\n\n"
        f"🦝 _Совет енота:_ Обязательно сверьтесь с ценами конкурентов перед выставлением!"
    )
    await message.answer(text, reply_markup=get_action_inline_kb(), parse_mode="Markdown")
    await state.clear()

# --- ЭКСПРЕСС-АНАЛИЗ НИШИ ---
@dp.message(F.text == "📈 Экспресс-анализ ниши")
@dp.callback_query(F.data == "act_niche")
async def start_niche_analysis(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(CalcState.waiting_for_niche_data)
    prompt = (
        "📈 **Экспресс-оценка ниши**\n\n"
        "Введите **4 числа через пробел**:\n"
        "1. Средняя цена в нише (₽)\n"
        "2. Себестоимость закупки (₽)\n"
        "3. Ожидаемый ДРР / Реклама (%)\n"
        "4. Планируемый объем (шт/мес)\n\n"
        "📋 _Пример:_ `1200 400 15 200`"
    )
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(prompt, reply_markup=get_cancel_inline_kb(), parse_mode="Markdown")
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

    est_fees = avg_price * 0.22 + 150 + (avg_price * 0.06)
    est_ad_costs = avg_price * (drr_pct / 100)
    
    unit_profit = avg_price - cost - est_fees - est_ad_costs
    total_revenue = avg_price * monthly_sales
    total_net_profit = unit_profit * monthly_sales
    required_capital = (cost * monthly_sales) + (monthly_sales * 100)

    if unit_profit <= 0:
        niche_verdict = "Высокий риск: Убытки при выбранной рекламной ставке."
        badge = "Тонущий корабль"
    elif unit_profit < 150:
        niche_verdict = "Низкая маржа: Потребуется большой объем или снижение закупки."
        badge = "Зона риска"
    else:
        niche_verdict = "Перспективно: Отличный запас прочности для старта."
        badge = "Золотая жила"

    text = (
        f"📈 **Потенциал ниши**\n"
        f"═══════════════════\n"
        f"💵 Средняя цена: **{avg_price:.2f} ₽**\n"
        f"📊 Оборот ({int(monthly_sales)} шт/мес): **{total_revenue:,.2f} ₽**\n\n"
        f"💰 Прибыль с 1 шт: **{unit_profit:.2f} ₽**\n"
        f"🏆 Чистая прибыль в месяц: **{total_net_profit:,.2f} ₽**\n"
        f"💼 Старт. капитал на партию: **{required_capital:,.2f} ₽**\n"
        f"═══════════════════\n"
        f"🏅 Статус ниши: **{badge}**\n"
        f"💡 {niche_verdict}"
    )

    categories = ['Капитал', 'Выручка', 'Прибыль']
    values = [required_capital, total_revenue, max(0, total_net_profit)]
    chart_buf = generate_bar_chart(categories, values, "Масштабы ниши в месяц (₽)")

    calc_id = f"n_{message.from_user.id}"
    user_last_calc[calc_id] = {
        'platform': 'Ниша',
        'table': {
            'Средняя цена': f"{avg_price:.2f} руб",
            'Закупка единицы': f"{cost:.2f} руб",
            'Продажи в месяц': f"{int(monthly_sales)} шт",
            'Месячный оборот': f"{total_revenue:,.2f} руб",
            'Чистая прибыль в месяц': f"{total_net_profit:,.2f} руб",
            'Стартовый капитал': f"{required_capital:,.2f} руб"
        },
        'badge': badge,
        'verdict': niche_verdict,
        'chart': chart_buf
    }

    photo = types.BufferedInputFile(chart_buf.getvalue(), filename="niche_chart.png")
    await message.answer_photo(photo, caption=text, reply_markup=get_action_inline_kb(calc_id), parse_mode="Markdown")

    await state.clear()

# --- СКАЧИВАНИЕ PDF ---
@dp.callback_query(F.data.startswith("pdf_"))
async def download_pdf_handler(callback: types.CallbackQuery):
    calc_id = callback.data.replace("pdf_", "")
    calc_data = user_last_calc.get(calc_id)

    if not calc_data:
        await callback.answer("⚠️ Данные устарели. Пожалуйста, сделайте расчёт заново.", show_alert=True)
        return

    await callback.answer("📄 Генерирую брендированный PDF-отчёт...")
    pdf_buf = create_pdf_report(calc_data, calc_data['chart'])
    
    doc_file = types.BufferedInputFile(pdf_buf.getvalue(), filename=f"Report_{calc_data.get('platform', 'Market')}.pdf")
    await callback.message.answer_document(doc_file, caption="Вот твой профессиональный PDF-отчёт! Можешь смело скидывать партнерам 🦝📄")

# --- FALLBACK ---
@dp.message()
async def fallback_handler(message: types.Message, state: FSMContext):
    parts = parse_numbers(message.text)
    if len(parts) >= 6:
        await process_margin_calc(message, state)
    else:
        await message.answer("🤖 Выберите команду в меню ниже или нажмите `/start`", reply_markup=get_main_keyboard())

# --- ВЕБ-СЕРВЕР DUMMY ДЛЯ RENDER ---
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
