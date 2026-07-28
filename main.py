from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Гарантированное подключение системного шрифта Linux ---
FONT_NAME = 'Helvetica'

def init_pdf_font():
    global FONT_NAME
    # Список стандартных путей к кириллическим шрифтам в Linux (Render)
    system_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "DejaVuSans.ttf"
    ]
    
    for font_path in system_fonts:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('CyrillicFont', font_path))
                FONT_NAME = 'CyrillicFont'
                print(f"Успешно подключен шрифт: {font_path}")
                return
            except Exception as e:
                print(f"Ошибка регистрации {font_path}: {e}")

    # Если системного файла нет, скачиваем напрямую с надежного зеркала
    try:
        if not os.path.exists("DejaVuSans.ttf"):
            import urllib.request
            url = "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf"
            urllib.request.urlretrieve(url, "DejaVuSans.ttf")
        
        pdfmetrics.registerFont(TTFont('CyrillicFont', "DejaVuSans.ttf"))
        FONT_NAME = 'CyrillicFont'
        print("Шрифт успешно загружен и зарегистрирован!")
    except Exception as e:
        print(f"Не удалось подключить шрифт: {e}")

init_pdf_font()

# --- Обновленный генератор PDF ---
def create_pdf_report(calc_data, chart_buf):
    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []

    styles = getSampleStyleSheet()
    
    # Принудительно применяем зарегистрированный FONT_NAME ко всем стилям
    title_style = ParagraphStyle('PdfTitle', parent=styles['Heading1'], fontName=FONT_NAME, fontSize=16, textColor=colors.HexColor('#1E1E2E'), spaceAfter=12)
    cell_style = ParagraphStyle('PdfCell', parent=styles['Normal'], fontName=FONT_NAME, fontSize=9, textColor=colors.HexColor('#333333'))
    header_style = ParagraphStyle('PdfHeader', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10, textColor=colors.whitesmoke)

    platform_name = calc_data.get('platform', 'Ozon')
    story.append(Paragraph(f"Финансовый отчёт Unit-Economics ({platform_name})", title_style))
    story.append(Spacer(1, 10))

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
    story.append(Spacer(1, 15))

    story.append(Paragraph(f"<b>Вердикт:</b> {calc_data['verdict']}", cell_style))
    story.append(Spacer(1, 15))

    if chart_buf:
        chart_buf.seek(0)
        img = Image(chart_buf, width=380, height=240)
        story.append(img)

    doc.build(story)
    pdf_buf.seek(0)
    return pdf_buf
