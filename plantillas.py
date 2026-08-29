"""
Generador de plantillas PDF con la marca de Integrated Healthcare Services.
Diseño formal tipo carta de consultorio (tamaño carta, membrete y pie fijos).
Pensadas para descargarse y enviarse como adjunto junto con un SMS.
"""
import os
import io
from datetime import date
from reportlab.lib.pagesizes import letter
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
LIGHT_BORDER = HexColor("#e5e7eb")

CLINICA_NOMBRE = "Integrated Healthcare Services"
CLINICA_UBICACION = "Miami / Hialeah, FL"
CLINICA_TELEFONO = "786-893-4314"

MARGIN = 0.85 * inch


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
    lineas = []
    for parrafo in text.split("\n"):
        palabras = parrafo.split()
        actual = ""
        if not palabras:
            lineas.append("")
            continue
        for palabra in palabras:
            prueba = (actual + " " + palabra).strip()
            if c.stringWidth(prueba, font, size) <= max_width:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = palabra
        if actual:
            lineas.append(actual)
    return lineas


def _membrete(c, W, H):
    """Encabezado formal: logo pequeño a la izquierda, datos de la clínica a la derecha, línea divisoria."""
    top = H - MARGIN
    logo_w = 1.5 * inch
    logo_h = _logo(c, MARGIN, top - 0.55 * inch, logo_w)

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(NAVY)
    c.drawRightString(W - MARGIN, top - 0.15 * inch, CLINICA_NOMBRE)
    c.setFont("Helvetica", 9)
    c.setFillColor(GRAY)
    c.drawRightString(W - MARGIN, top - 0.32 * inch, CLINICA_UBICACION)
    c.drawRightString(W - MARGIN, top - 0.46 * inch, f"Tel: {CLINICA_TELEFONO}")

    linea_y = top - max(logo_h, 0.6 * inch) - 0.12 * inch
    c.setStrokeColor(GREEN)
    c.setLineWidth(1.4)
    c.line(MARGIN, linea_y, W - MARGIN, linea_y)
    return linea_y - 0.35 * inch


def _pie_pagina(c, W):
    y = MARGIN - 0.15 * inch
    c.setStrokeColor(LIGHT_BORDER)
    c.setLineWidth(0.8)
    c.line(MARGIN, y + 0.28 * inch, W - MARGIN, y + 0.28 * inch)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(GRAY)
    c.drawCentredString(W / 2, y + 0.12 * inch,
                         f"{CLINICA_NOMBRE}  -  {CLINICA_UBICACION}  -  Tel: {CLINICA_TELEFONO}")
    c.setFont("Helvetica-Oblique", 8.5)
    c.drawCentredString(W / 2, y - 0.02 * inch, "Su confianza es nuestra prioridad")


def _fecha_formato_largo(fecha_iso):
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    try:
        y, m, d = fecha_iso.split("-")
        return f"{int(d)} de {meses[int(m) - 1]} de {y}"
    except Exception:
        return fecha_iso


def _carta_base(titulo_documento):
    buf = io.BytesIO()
    W, H = letter
    c = canvas.Canvas(buf, pagesize=(W, H))
    y = _membrete(c, W, H)

    c.setFont("Helvetica-Bold", 15)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, titulo_documento.upper())
    y -= 0.35 * inch
    return buf, c, W, H, y


def _cerrar_carta(buf, c, W):
    _pie_pagina(c, W)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _parrafo(c, texto, x, y, max_width, font="Times-Roman", size=11, leading=15.5, color=NAVY):
    c.setFillColor(color)
    for linea in _wrap_text(c, texto, font, size, max_width):
        c.setFont(font, size)
        c.drawString(x, y, linea)
        y -= leading
    return y


def _rect_dato(c, x, y, w, h, etiqueta, valor):
    c.setFillColor(GREEN_LIGHT)
    c.roundRect(x, y, w, h, 6, fill=1, stroke=0)
    c.setFillColor(GRAY)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 14, y + h - 16, etiqueta.upper())
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x + 14, y + h - 38, str(valor))


# ---------------------------------------------------------------
# 1. AVISO DE PAGO (carta formal)
# ---------------------------------------------------------------
def generar_aviso_pago(paciente="", monto="", telefono=CLINICA_TELEFONO):
    buf, c, W, H, y = _carta_base("Aviso de Pago")
    ancho_texto = W - 2 * MARGIN

    c.setFont("Times-Roman", 11)
    c.setFillColor(GRAY)
    c.drawString(MARGIN, y, _fecha_formato_largo(date.today().isoformat()))
    y -= 0.35 * inch

    saludo = f"Estimado(a) {paciente}:" if paciente else "Estimado(a) paciente:"
    c.setFont("Times-Bold", 12)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, saludo)
    y -= 0.32 * inch

    cuerpo = ("Le escribimos para recordarle amablemente que tiene un balance pendiente con nuestra "
              "oficina. Le agradecemos gestionar su pago a la brevedad posible para mantener su cuenta al día.")
    y = _parrafo(c, cuerpo, MARGIN, y, ancho_texto)
    y -= 0.15 * inch

    if monto:
        _rect_dato(c, MARGIN, y - 0.65 * inch, ancho_texto, 0.65 * inch, "Monto adeudado", f"${monto}")
        y -= 0.75 * inch

    y -= 0.1 * inch
    c.setFont("Times-Bold", 11)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, "Por favor, dirija su pago a nombre de:")
    y -= 0.26 * inch
    c.setFont("Times-Bold", 13)
    c.setFillColor(GREEN)
    c.drawString(MARGIN, y, CLINICA_NOMBRE)
    y -= 0.4 * inch

    cuerpo2 = (f"Aceptamos pagos con tarjeta débito/crédito y Zelle. Si tiene alguna pregunta sobre este "
               f"balance o desea coordinar un plan de pago, no dude en comunicarse con nosotros al {telefono}.")
    y = _parrafo(c, cuerpo2, MARGIN, y, ancho_texto)
    y -= 0.45 * inch

    c.setFont("Times-Roman", 11)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, "Atentamente,")
    y -= 0.55 * inch
    c.setFont("Times-Bold", 11)
    c.drawString(MARGIN, y, CLINICA_NOMBRE)

    return _cerrar_carta(buf, c, W)


# ---------------------------------------------------------------
# 2. CONFIRMACIÓN DE CITA (carta formal)
# ---------------------------------------------------------------
def generar_confirmacion_cita(paciente="", fecha="", hora="", proveedor="",
                               ubicacion=CLINICA_UBICACION, telefono=CLINICA_TELEFONO):
    buf, c, W, H, y = _carta_base("Confirmación de Cita")
    ancho_texto = W - 2 * MARGIN

    c.setFont("Times-Roman", 11)
    c.setFillColor(GRAY)
    c.drawString(MARGIN, y, _fecha_formato_largo(date.today().isoformat()))
    y -= 0.35 * inch

    saludo = f"Estimado(a) {paciente}:" if paciente else "Estimado(a) paciente:"
    c.setFont("Times-Bold", 12)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, saludo)
    y -= 0.32 * inch

    y = _parrafo(c, "Confirmamos los detalles de su próxima cita con nosotros:", MARGIN, y, ancho_texto)
    y -= 0.25 * inch

    datos = [
        ("Fecha", _fecha_formato_largo(fecha) if fecha else "Por confirmar"),
        ("Hora", hora or "Por confirmar"),
        ("Proveedor", proveedor or "Por asignar"),
        ("Ubicación", ubicacion),
    ]
    row_h = 0.4 * inch
    for etiqueta, valor in datos:
        c.setFillColor(GREEN_LIGHT)
        c.roundRect(MARGIN, y - row_h, ancho_texto, row_h - 6, 5, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(MARGIN + 14, y - row_h + 15, f"{etiqueta}:")
        c.setFont("Helvetica", 10.5)
        c.drawString(MARGIN + 130, y - row_h + 15, str(valor))
        y -= row_h

    y -= 0.25 * inch
    cuerpo2 = (f"Le solicitamos llegar 10 minutos antes de su cita. Si necesita cancelar o reprogramar, "
               f"le agradecemos avisarnos con al menos 24 horas de anticipación llamando al {telefono}.")
    y = _parrafo(c, cuerpo2, MARGIN, y, ancho_texto)
    y -= 0.45 * inch

    c.setFont("Times-Roman", 11)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, "Atentamente,")
    y -= 0.55 * inch
    c.setFont("Times-Bold", 11)
    c.drawString(MARGIN, y, CLINICA_NOMBRE)

    return _cerrar_carta(buf, c, W)


# ---------------------------------------------------------------
# 3. RECIBO DE PAGO (carta formal — confirma un pago ya realizado)
# ---------------------------------------------------------------
def generar_recibo_pago(paciente="", concepto="", monto="", metodo="", fecha=""):
    buf, c, W, H, y = _carta_base("Recibo de Pago")
    ancho_texto = W - 2 * MARGIN

    fecha_mostrar = fecha or date.today().isoformat()
    c.setFont("Times-Roman", 11)
    c.setFillColor(GRAY)
    c.drawString(MARGIN, y, _fecha_formato_largo(fecha_mostrar))
    y -= 0.35 * inch

    saludo = f"Estimado(a) {paciente}:" if paciente else "Estimado(a) paciente:"
    c.setFont("Times-Bold", 12)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, saludo)
    y -= 0.32 * inch

    y = _parrafo(c, "Confirmamos que hemos recibido su pago con los siguientes detalles:",
                 MARGIN, y, ancho_texto)
    y -= 0.25 * inch

    datos = [
        ("Concepto", concepto or "Servicios prestados"),
        ("Método de pago", metodo or "No especificado"),
        ("Fecha de pago", _fecha_formato_largo(fecha_mostrar)),
    ]
    row_h = 0.4 * inch
    for etiqueta, valor in datos:
        c.setFillColor(GREEN_LIGHT)
        c.roundRect(MARGIN, y - row_h, ancho_texto, row_h - 6, 5, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(MARGIN + 14, y - row_h + 15, f"{etiqueta}:")
        c.setFont("Helvetica", 10.5)
        c.drawString(MARGIN + 160, y - row_h + 15, str(valor))
        y -= row_h

    y -= 0.15 * inch
    _rect_dato(c, MARGIN, y - 0.65 * inch, ancho_texto, 0.65 * inch, "Monto pagado",
               f"${monto}" if monto else "$0.00")
    y -= 0.9 * inch

    y = _parrafo(c, "Gracias por su pago y por confiar en nosotros para su cuidado. "
                    "Conserve este recibo para su récord.", MARGIN, y, ancho_texto)
    y -= 0.45 * inch

    c.setFont("Times-Roman", 11)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, "Atentamente,")
    y -= 0.55 * inch
    c.setFont("Times-Bold", 11)
    c.drawString(MARGIN, y, CLINICA_NOMBRE)

    return _cerrar_carta(buf, c, W)


# ---------------------------------------------------------------
# 4. CARTA PERSONALIZADA — plantilla libre: escribe cualquier asunto y
#    cuerpo, y se genera con el mismo membrete/pie formal de la clínica.
#    Esto permite crear "nuevas plantillas" sin tocar código.
# ---------------------------------------------------------------
def generar_carta_personalizada(asunto="Comunicado", cuerpo="", paciente=""):
    buf, c, W, H, y = _carta_base(asunto or "Comunicado")
    ancho_texto = W - 2 * MARGIN

    c.setFont("Times-Roman", 11)
    c.setFillColor(GRAY)
    c.drawString(MARGIN, y, _fecha_formato_largo(date.today().isoformat()))
    y -= 0.35 * inch

    if paciente:
        c.setFont("Times-Bold", 12)
        c.setFillColor(NAVY)
        c.drawString(MARGIN, y, f"Estimado(a) {paciente}:")
        y -= 0.32 * inch

    texto = cuerpo or "Escriba aquí el contenido de su comunicado."
    y = _parrafo(c, texto, MARGIN, y, ancho_texto, leading=16)
    y -= 0.5 * inch

    c.setFont("Times-Roman", 11)
    c.setFillColor(NAVY)
    c.drawString(MARGIN, y, "Atentamente,")
    y -= 0.55 * inch
    c.setFont("Times-Bold", 11)
    c.drawString(MARGIN, y, CLINICA_NOMBRE)

    return _cerrar_carta(buf, c, W)


# ---------------------------------------------------------------
# 5. PROMOCIÓN / FLYER (formato mercadeo — no es una carta formal)
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

    logo_w = 2.6 * inch
    logo_h = _logo(c, margin, H - margin - 1.0 * inch, logo_w)
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Oblique", 16)
    c.drawString(margin, H - margin - 1.0 * inch - 22, "Wellness Center")

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(margin, H - margin - 1.7 * inch, titulo)

    y = H - margin - 2.2 * inch
    row_h = 0.62 * inch
    for nombre, precio in items:
        c.setFillColor(WHITE)
        c.setStrokeColor(LIGHT_BORDER)
        c.roundRect(margin, y - row_h, W - 2 * margin - 1.6 * inch, row_h, 8, fill=1, stroke=1)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin + 14, y - row_h / 2 - 5, nombre)
        c.setFillColor(GREEN)
        c.roundRect(W - margin - 1.5 * inch, y - row_h + 6, 1.5 * inch, row_h - 12, 8, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(W - margin - 0.75 * inch, y - row_h / 2 - 5, precio)
        y -= row_h + 10

    bar_h = 0.5 * inch
    c.setFillColor(NAVY)
    c.roundRect(margin, margin + 0.55 * inch, W - 2 * margin, bar_h, 10, fill=1, stroke=0)
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
