"""
Generador de plantillas PDF con la marca de Integrated Healthcare Services.
Pensadas para descargarse y enviarse como adjunto junto con un SMS.
"""
import os
import io
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "static", "branding", "logo.png")

NAVY = HexColor("#001a42")
GREEN = HexColor("#1f6b2b")
GREEN_LIGHT = HexColor("#eaf5e8")
WHITE = HexColor("#ffffff")
GRAY = HexColor("#6b7280")


def _rounded_rect(c, x, y, w, h, r, fill=None, stroke=None, stroke_width=1.2):
    c.saveState()
    if fill:
        c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(stroke_width)
    c.roundRect(x, y, w, h, r, fill=1 if fill else 0, stroke=1 if stroke else 0)
    c.restoreState()


def _logo(c, x, y, w):
    try:
        img = ImageReader(LOGO_PATH)
        iw, ih = img.getSize()
        h = w * ih / iw
        c.drawImage(img, x, y, width=w, height=h, mask='auto')
        return h
    except Exception:
        return 0


def _wrap_text(c, text, font, size, max_width):
    c.setFont(font, size)
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = (current + " " + word).strip()
        if c.stringWidth(trial, font, size) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------
# 1. AVISO DE PAGO
# ---------------------------------------------------------------
def generar_aviso_pago(paciente="", monto="", telefono="786-893-4314"):
    buf = io.BytesIO()
    W, H = landscape(letter)
    c = canvas.Canvas(buf, pagesize=(W, H))

    margin = 0.4 * inch
    _rounded_rect(c, margin, margin, W - 2 * margin, H - 2 * margin, 14, fill=WHITE, stroke=GREEN, stroke_width=2)

    # Header bar
    bar_h = 0.65 * inch
    bar_y = H - margin - 0.35 * inch - bar_h
    _rounded_rect(c, margin + 0.3 * inch, bar_y, W - 2 * margin - 0.6 * inch, bar_h, 10, fill=NAVY)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(W / 2, bar_y + bar_h / 2 - 7, "DIRIGIR SUS PAGOS A")

    # Logo
    logo_w = 2.4 * inch
    logo_h = _logo(c, W / 2 - logo_w / 2, bar_y - 1.15 * inch, logo_w)

    # Confirmation box
    box_y = bar_y - 1.15 * inch - logo_h - 0.75 * inch
    box_h = 0.95 * inch
    _rounded_rect(c, margin + 0.3 * inch, box_y, W - 2 * margin - 0.6 * inch, box_h, 10, fill=GREEN)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(W / 2, box_y + box_h - 20, "CONFIRME QUE EL NOMBRE DE LA COMPAÑÍA COINCIDA:")
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(HexColor("#c8e6a0"))
    c.drawCentredString(W / 2, box_y + 14, "Integrated Healthcare Services")

    # Patient / amount (optional)
    info_y = box_y - 0.35 * inch
    c.setFillColor(NAVY)
    c.setFont("Helvetica", 12)
    if paciente:
        c.drawCentredString(W / 2, info_y, f"Paciente: {paciente}")
        info_y -= 0.22 * inch
    if monto:
        c.drawCentredString(W / 2, info_y, f"Monto a pagar: ${monto}")
        info_y -= 0.22 * inch

    # Phone
    c.setFont("Helvetica-Bold", 26)
    c.setFillColor(NAVY)
    c.drawCentredString(W / 2, margin + 0.55 * inch, telefono)

    # Footer
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(GRAY)
    c.drawCentredString(W / 2, margin + 0.2 * inch, "SU CONFIANZA ES NUESTRA PRIORIDAD")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf


# ---------------------------------------------------------------
# 2. CONFIRMACIÓN DE CITA
# ---------------------------------------------------------------
def generar_confirmacion_cita(paciente="", fecha="", hora="", proveedor="", ubicacion="Miami / Hialeah, FL", telefono="786-893-4314"):
    buf = io.BytesIO()
    W, H = landscape(letter)
    c = canvas.Canvas(buf, pagesize=(W, H))

    margin = 0.4 * inch
    _rounded_rect(c, margin, margin, W - 2 * margin, H - 2 * margin, 14, fill=WHITE, stroke=NAVY, stroke_width=2)

    bar_h = 0.65 * inch
    bar_y = H - margin - 0.35 * inch - bar_h
    _rounded_rect(c, margin + 0.3 * inch, bar_y, W - 2 * margin - 0.6 * inch, bar_h, 10, fill=GREEN)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(W / 2, bar_y + bar_h / 2 - 7, "CONFIRMACIÓN DE CITA")

    logo_w = 2.2 * inch
    logo_h = _logo(c, W / 2 - logo_w / 2, bar_y - 1.05 * inch, logo_w)

    rows = [
        ("Paciente", paciente or "____________________"),
        ("Fecha", fecha or "____________________"),
        ("Hora", hora or "____________________"),
        ("Proveedor", proveedor or "____________________"),
        ("Ubicación", ubicacion),
    ]
    y = bar_y - 1.05 * inch - logo_h - 0.5 * inch
    row_h = 0.42 * inch
    table_x = margin + 0.6 * inch
    table_w = W - 2 * margin - 1.2 * inch
    for label, value in rows:
        _rounded_rect(c, table_x, y - row_h, table_w, row_h, 6, fill=GREEN_LIGHT)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(table_x + 14, y - row_h + 13, f"{label}:")
        c.setFont("Helvetica", 11)
        c.drawString(table_x + 130, y - row_h + 13, str(value))
        y -= row_h + 8

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(NAVY)
    c.drawCentredString(W / 2, margin + 0.55 * inch, f"¿Necesita reprogramar? Llámenos al {telefono}")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(GRAY)
    c.drawCentredString(W / 2, margin + 0.2 * inch, "SU CONFIANZA ES NUESTRA PRIORIDAD")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf


# ---------------------------------------------------------------
# 3. PROMOCIÓN / FLYER (formato carta completa)
# ---------------------------------------------------------------
def generar_promocion(titulo="WEIGHT LOSS PROGRAM", items=None, telefono="786-536-1701", texto_sms="305-394-8297"):
    if items is None:
        items = [
            ("Fat Burner Shot + B12", "$25 / semana"),
            ("Vitamin B12 Shot", "$15 / semana"),
            ("Vitamin Complex", "$20 / semana"),
            ("NAD+ Anti-Aging & Energy", "$30 / semana"),
            ("Glutathione Injection", "$35 / semana"),
        ]
    buf = io.BytesIO()
    W, H = letter
    c = canvas.Canvas(buf, pagesize=(W, H))
    margin = 0.5 * inch

    # Header
    logo_w = 2.6 * inch
    logo_h = _logo(c, margin, H - margin - 1.0 * inch, logo_w)
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Oblique", 16)
    c.drawString(margin, H - margin - 1.0 * inch - 22, "Wellness Center")

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(margin, H - margin - 1.7 * inch, titulo)

    # Items
    y = H - margin - 2.2 * inch
    row_h = 0.62 * inch
    for nombre, precio in items:
        _rounded_rect(c, margin, y - row_h, W - 2 * margin - 1.6 * inch, row_h, 8, fill=WHITE, stroke=HexColor("#e5e7eb"))
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin + 14, y - row_h / 2 - 5, nombre)
        _rounded_rect(c, W - margin - 1.5 * inch, y - row_h + 6, 1.5 * inch, row_h - 12, 8, fill=GREEN)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(W - margin - 0.75 * inch, y - row_h / 2 - 5, precio)
        y -= row_h + 10

    # Contact bar
    bar_h = 0.5 * inch
    _rounded_rect(c, margin, margin + 0.55 * inch, W - 2 * margin, bar_h, 10, fill=NAVY)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(W / 2, margin + 0.55 * inch + bar_h / 2 - 5,
                         f"CALL {telefono}   |   TEXT {texto_sms}")

    c.setFillColor(GRAY)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(W / 2, margin + 0.2 * inch, "Invierta en su salud... nos importa su bienestar")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
