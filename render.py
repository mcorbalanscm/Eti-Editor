# -*- coding: utf-8 -*-
"""
render.py
Renderiza un Diseno a una imagen PIL, independientemente de la GUI.
Se usa tanto para "Imprimir" como para "Exportar a PNG/PDF".
"""

from PIL import Image, ImageDraw, ImageFont
import io
import os
import re

from eti_format import RATIO_MM_A_PX

try:
    import barcode as barcode_lib
    from barcode.writer import ImageWriter
    HAY_BARCODE = True
except ImportError:
    HAY_BARCODE = False


_BARCODE_MAP = {
    "Code128": "code128",
    "Code128C": "code128",
    "Code39": "code39",
    "EAN13": "ean13",
    "EAN8": "ean8",
    "UPCA": "upca",
    "ITF": "itf",
}


# ---------------------------------------------------------------------------
# Campos variables ("A000FECALT", "A130NUMDOC"...) y datos de ejemplo (mock)
# ---------------------------------------------------------------------------
# Estas etiquetas usan un convenio de nombre de campo: una letra + 3 dígitos +
# el nombre abreviado del campo en mayúsculas (p.ej. A000FECALT = fecha alta).
# En el editor no tenemos datos reales de la base de datos que los rellena,
# así que para la vista previa / impresión los sustituimos por datos de
# ejemplo para hacerse una idea aproximada del resultado final.
_RE_CAMPO_VARIABLE = re.compile(r"^[A-Z]\d{3}[A-Z]{2,}\d*$")

_MOCK_BARRAS_POR_ENCODING = {
    "EAN13": "590123412345",
    "EAN8": "9638507",
    "UPCA": "03600029145",
}


def es_campo_variable(texto):
    """True si `texto` parece un código de campo variable (no texto literal)."""
    return bool(texto) and bool(_RE_CAMPO_VARIABLE.match(texto.strip()))


def valor_mock_texto(texto):
    """Genera un valor de ejemplo del mismo largo aproximado que el original,
    para poder ver si el texto real cabrá en el hueco reservado."""
    largo = max(4, min(len(texto), 16))
    return "X" * largo


def valor_mock_barras(cb):
    """Genera un código de ejemplo válido para la codificación del código de barras."""
    if cb.codificacion in _MOCK_BARRAS_POR_ENCODING:
        return _MOCK_BARRAS_POR_ENCODING[cb.codificacion]
    largo = max(6, min(len(cb.codigo), 18))
    base = "1234567890"
    return (base * ((largo // len(base)) + 1))[:largo]


def _cargar_fuente(nombre, tamano):
    """Intenta encontrar una fuente TTF razonable; si no, usa la por defecto."""
    candidatos = [
        nombre,
        nombre.lower(),
        f"{nombre}.ttf",
        f"{nombre.lower()}.ttf",
        "DejaVuSans.ttf",
        "Arial.ttf",
        "arial.ttf",
    ]
    rutas_extra = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for c in candidatos:
        try:
            return ImageFont.truetype(c, tamano)
        except Exception:
            continue
    for r in rutas_extra:
        if os.path.exists(r):
            try:
                return ImageFont.truetype(r, tamano)
            except Exception:
                continue
    return ImageFont.load_default()


def generar_imagen_codigo_barras(cb, codigo_override=None):
    """Devuelve una imagen PIL con el código de barras (o None si falla).
    `codigo_override` permite generar el gráfico con un valor distinto al
    guardado en el diseño (usado para la vista previa con datos de ejemplo)."""
    if not HAY_BARCODE:
        return None
    clase = _BARCODE_MAP.get(cb.codificacion, "code128")
    valor = codigo_override if codigo_override is not None else cb.codigo
    try:
        BarClass = barcode_lib.get_barcode_class(clase)
        writer = ImageWriter()
        writer.dpi = 203
        bc = BarClass(valor, writer=writer)
        buf = io.BytesIO()
        opciones = {
            "write_text": cb.human_valor,
            "module_height": max(5.0, cb.alto / 4.0),
            "quiet_zone": 1.0,
        }
        bc.write(buf, options=opciones)
        buf.seek(0)
        img = Image.open(buf)
        img.load()
        return img
    except Exception:
        return None


def render_diseno(diseno, escala=1.0, fondo="white", usar_datos_mock=False):
    """
    Renderiza el diseño completo a una imagen PIL.

    El tamaño de la imagen es SIEMPRE el de la etiqueta configurada
    (diseno.ancho x diseno.alto, en mm) convertido a píxeles con el mismo
    factor que usaba el diseñador original (RATIO_MM_A_PX = 3.4), multiplicado
    por `escala` para obtener más resolución si se desea (para imprimir o
    exportar con calidad). El tamaño de hoja NUNCA se agranda por el
    contenido: cualquier elemento que sobresalga de esa área queda recortado,
    igual que en el programa original.

    IMPORTANTE: ese factor 3.4 sólo se aplica al tamaño de la HOJA (mm -> px).
    Las coordenadas x/y/w/h de los elementos ya están en píxeles dentro del
    .eti, así que NO se multiplican por 3.4, solo por `escala`.

    Si `usar_datos_mock` es True, los campos variables (tipo A000FECALT)
    se sustituyen por datos de ejemplo, tanto en textos como en códigos
    de barras, para poder previsualizar/imprimir un resultado realista.
    """
    ancho_px = max(1, int(round(diseno.ancho * RATIO_MM_A_PX * escala)))
    alto_px = max(1, int(round(diseno.alto * RATIO_MM_A_PX * escala)))
    img = Image.new("RGB", (ancho_px, alto_px), fondo)
    draw = ImageDraw.Draw(img)

    def tx(x):
        return x * escala

    def ty(y):
        return y * escala

    # Formas primero (quedan "debajo")
    for fm in diseno.formas:
        x0f, y0f = tx(fm.x), ty(fm.y)
        x1f, y1f = tx(fm.x + fm.w), ty(fm.y + fm.h)
        ancho_linea = max(1, int(fm.grosor * escala))
        relleno = fm.color if fm.relleno else None
        if fm.tipo == "linea":
            draw.line([x0f, y0f, x1f, y1f], fill=fm.color, width=ancho_linea)
        elif fm.tipo == "rectangulo":
            draw.rectangle([x0f, y0f, x1f, y1f], outline=fm.color,
                            fill=relleno, width=ancho_linea)
        elif fm.tipo == "circulo":
            draw.ellipse([x0f, y0f, x1f, y1f], outline=fm.color,
                         fill=relleno, width=ancho_linea)

    # Imágenes
    for im in diseno.imagenes:
        if im.ruta and os.path.exists(im.ruta):
            try:
                pic = Image.open(im.ruta).convert("RGBA")
                w = max(1, int(im.w * escala))
                h = max(1, int(im.h * escala))
                pic = pic.resize((w, h))
                if im.rotacion:
                    pic = pic.rotate(-im.rotacion, expand=True)
                img.paste(pic, (int(tx(im.x)), int(ty(im.y))), pic)
            except Exception:
                pass

    # Códigos de barras
    for cb in diseno.barras:
        codigo_efectivo = cb.codigo
        if usar_datos_mock and es_campo_variable(cb.codigo):
            codigo_efectivo = valor_mock_barras(cb)
        bimg = generar_imagen_codigo_barras(cb, codigo_override=codigo_efectivo)
        w = max(1, int(cb.w * escala))
        h = max(1, int(cb.h * escala))
        if bimg is not None:
            bimg = bimg.convert("RGB").resize((w, h))
            img.paste(bimg, (int(tx(cb.x)), int(ty(cb.y))))
        else:
            draw.rectangle([tx(cb.x), ty(cb.y), tx(cb.x) + w, ty(cb.y) + h],
                            outline="black", width=2)
            draw.text((tx(cb.x) + 4, ty(cb.y) + h // 2 - 6),
                       f"[{codigo_efectivo}]", fill="black")

    # Textos (por encima, para que se vean siempre)
    for lit in diseno.literales:
        texto_efectivo = lit.texto
        if usar_datos_mock and es_campo_variable(lit.texto):
            texto_efectivo = valor_mock_texto(lit.texto)
        fuente = _cargar_fuente(lit.fuente, max(6, int(lit.tamano_letra * escala)))
        txt_img = Image.new("RGBA", (max(1, int(lit.w * escala)), max(1, int(lit.h * escala))), (255, 255, 255, 0))
        tdraw = ImageDraw.Draw(txt_img)
        tdraw.text((0, 0), texto_efectivo, font=fuente, fill="black")
        if lit.rotacion:
            txt_img = txt_img.rotate(lit.rotacion, expand=True)
        img.paste(txt_img, (int(tx(lit.x)), int(ty(lit.y))), txt_img)

    return img


def exportar_png(diseno, path, escala=2.0, usar_datos_mock=False):
    img = render_diseno(diseno, escala=escala, usar_datos_mock=usar_datos_mock)
    img.save(path, "PNG")
    return path


def exportar_pdf(diseno, path, escala=2.0, usar_datos_mock=False):
    img = render_diseno(diseno, escala=escala, usar_datos_mock=usar_datos_mock).convert("RGB")
    img.save(path, "PDF")
    return path